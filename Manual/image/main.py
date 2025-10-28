import base64
import os
import random

import kopf
import kubernetes
import yaml
from kubernetes.client.rest import ApiException

'''
启动的时候，自动应用CRD
'''


@kopf.on.startup()
def apply_crd(logger, settings, **kwargs):
    settings.peering.name = "kube-user-manage"
    settings.peering.priority = random.randint(0, 32767)
    settings.watching.client_timeout = 60
    settings.watching.server_timeout = 60
    configuration = kubernetes.config.load_incluster_config()
    crds = ['template/crd.yaml', 'template/lu-config-crd.yaml']
    api = kubernetes.client.ApiextensionsV1Api(configuration)
    for crd in crds:
        path = os.path.join(os.path.dirname(__file__), crd)
        text = open(path, 'rt').read()
        data = yaml.safe_load(text)

        try:
            api.read_custom_resource_definition(name=data['metadata']['name'])
            logger.info(f"crd already exist: {data['metadata']['name']}")
        except ApiException as e:
            if e.reason == "Conflict":
                logger.info("%s\n" % e.body)
            else:
                api.create_custom_resource_definition(body=data)

    return {'crd_status': True}


'''
创建账号信息，并绑定
'''


@kopf.on.create('lensuser', group='osip.cc', version='v1')
def create_lu(spec, name, namespace, logger, **kwargs):
    roles = spec.get('roles')
    if not roles:
        raise kopf.PermanentError(f"roles must be set. Got {roles!r}.")

    path = os.path.join(os.path.dirname(__file__), 'template/sa.yaml')
    tmpl = open(path, 'rt').read()
    text = tmpl.format(name=name)
    data = yaml.safe_load(text)
    kopf.adopt(data)
    api = kubernetes.client.CoreV1Api()

    try:
        api.create_namespaced_service_account(
            namespace=namespace,
            body=data,
        )
    except ApiException as e:
        if e.reason == "Conflict":
            logger.info("%s\n" % e.body)
        else:
            raise kopf.PermanentError(f"service account create failed. name {roles!r}.")

    api = kubernetes.client.RbacAuthorizationV1Api()
    for role in roles:
        path = os.path.join(os.path.dirname(__file__), 'template/rolebinding.yaml')
        tmpl = open(path, 'rt').read()
        text = tmpl.format(sa_name=name, sa_namespace=namespace, role_name=role.get('name'))
        data = yaml.safe_load(text)

        try:
            api.create_namespaced_role_binding(
                namespace=role.get('namespace'),
                body=data,
            )
        except ApiException as e:
            if e.reason == "Conflict":
                logger.info("%s\n" % e.body)
            else:
                raise kopf.PermanentError(f"service account create failed. name {roles!r}.")

    api = kubernetes.client.CoreV1Api()
    api_client = kubernetes.client.ApiClient()
    
    # 检查是否有自动生成的 secret
    sa = api.read_namespaced_service_account(name=name, namespace=namespace)
    if not sa.secrets:
        # 1.24+ 版本，手动创建永久 token secret
        try:
            # 使用 template 创建 Secret
            path = os.path.join(os.path.dirname(__file__), 'template/secret.yaml')
            tmpl = open(path, 'rt').read()
            text = tmpl.format(name=name, namespace=namespace)
            data = yaml.safe_load(text)
            kopf.adopt(data)
            
            # 创建 Secret
            secret = api.create_namespaced_secret(
                namespace=namespace,
                body=data
            )
            
            # 将 Secret 绑定到 ServiceAccount 的 secrets 字段
            try:
                # 直接更新 ServiceAccount，添加 secret 引用
                secret_ref = kubernetes.client.V1ObjectReference(
                    name=f"{name}-token",
                    namespace=namespace
                )
                
                # 使用 patch 操作添加 secret 引用
                patch_body = {
                    "secrets": [secret_ref]
                }
                
                api.patch_namespaced_service_account(
                    name=name,
                    namespace=namespace,
                    body=patch_body
                )
                
                sa_secret_name = f"{name}-token"
                
                logger.info(f"Successfully bound secret {name}-token to ServiceAccount {name}")
                
            except Exception as e:
                logger.error(f"Failed to bind secret to ServiceAccount: {e}")
            
        except Exception as e:
            logger.error(f"Failed to create token secret: {e}")
            raise kopf.PermanentError(f"Token secret creation failed: {e}")
    else:
        # 兼容旧版本，使用自动生成的 secret
        sa_secret_name = sa.secrets[-1]['name']

    secret_info = api_client.sanitize_for_serialization(api.read_namespaced_secret(name=sa_secret_name,namespace=namespace).data)
    path = os.path.join(os.path.dirname(__file__), 'template/kube-config.yaml')
    tmpl = open(path, 'rt').read()
    kube_config = tmpl.format(
        user_name=name,
        namespace=namespace,
        cluster_name=os.getenv('cluster_name'),
        api_url=os.getenv('kube_api_url'),
        ca=secret_info.get('ca.crt', 'NULL'),
        token=base64.b64decode(secret_info.get('token', 'NULL').encode('utf-8')).decode('utf-8'))

    logger.info(f"sa info:\n{kube_config}")

    crd_api = kubernetes.client.CustomObjectsApi()

    crd_api.create_namespaced_custom_object(
        group='osip.cc',
        version='v1',
        namespace=namespace,
        plural='luconfig',
        body=yaml.safe_load(kube_config)
    )

    return {'sa-name': name}


'''
更新权限信息
'''


@kopf.on.field('lensuser', group='osip.cc', version='v1', field='spec.roles')
def update_lu(diff, name, namespace, logger, **kwargs):
    for op, field, old, new in diff:
        if op != "change":
            return True

        if len(new) > len(old):
            for n in new:
                if n not in old:
                    api = kubernetes.client.RbacAuthorizationV1Api()
                    path = os.path.join(os.path.dirname(__file__), 'template/rolebinding.yaml')
                    tmpl = open(path, 'rt').read()
                    text = tmpl.format(sa_name=name, sa_namespace=namespace, role_name=n.get('name'))
                    data = yaml.safe_load(text)
                    try:
                        api.create_namespaced_role_binding(
                            namespace=n.get('namespace'),
                            body=data,
                        )
                    except ApiException as e:
                        if e.reason == "Conflict":
                            logger.info("%s\n" % e.body)
                        else:
                            raise kopf.PermanentError(f"service account create failed. name {n!r}.")
        elif len(new) < len(old):
            for o in old:
                if o not in new:
                    api = kubernetes.client.RbacAuthorizationV1Api()
                    try:
                        api.delete_namespaced_role_binding(
                            name=name,
                            namespace=o.get('namespace')
                        )
                    except ApiException as e:
                        logger.info("%s\n" % e.body)
                        raise kopf.PermanentError(f"service account delete failed. name {o!r}.")
        elif len(new) == len(old):
            for n in new:
                if n not in old:
                    api = kubernetes.client.RbacAuthorizationV1Api()
                    path = os.path.join(os.path.dirname(__file__), 'template/rolebinding.yaml')
                    tmpl = open(path, 'rt').read()
                    text = tmpl.format(sa_name=name, sa_namespace=namespace, role_name=n.get('name'))
                    data = yaml.safe_load(text)
                    try:
                        try:
                            api.delete_namespaced_role_binding(
                                name=name,
                                namespace=n.get('namespace')
                            )
                        except ApiException as e:
                            if e.reason == "NotFound":
                                logger.info("%s\n" % e.body)
                        api.create_namespaced_role_binding(
                            namespace=n.get('namespace'),
                            body=data,
                        )
                    except ApiException as e:
                        if e.reason == "Conflict":
                            logger.info("%s\n" % e.body)
                        else:
                            raise kopf.PermanentError(f"service account create failed. name {n!r}.")
            new_namespaces = {item['namespace'] for item in new}
            old_namespaces_not_in_new = [item for item in old if item['namespace'] not in new_namespaces]
            for del_role_bind in old_namespaces_not_in_new:
                try:
                    api.delete_namespaced_role_binding(
                    name=name,
                    namespace=del_role_bind.get('namespace')
                )
                except ApiException as e:
                    raise kopf.PermanentError(f"service account create failed. name {n!r}.")

    return {'sa-name': name}


@kopf.on.delete('lensuser', group='osip.cc', version='v1')
def delete_lu(spec, name, namespace, logger, **kwargs):
    roles = spec.get('roles')
    if not roles:
        raise kopf.PermanentError(f"roles must be set. Got {roles!r}.")

    api = kubernetes.client.RbacAuthorizationV1Api()
    for role in roles:
        try:
            api.delete_namespaced_role_binding(
                namespace=role.get('namespace'),
                name=name
            )
        except ApiException as e:
            logger.info("%s\n" % e.body)

    crd_api = kubernetes.client.CustomObjectsApi()
    try:
        crd_api.delete_namespaced_custom_object(
            group='osip.cc',
            version='v1',
            namespace=namespace,
            plural='luconfig',
            name=name
        )
    except ApiException as e:
        logger.info("%s\n" % e.body)
