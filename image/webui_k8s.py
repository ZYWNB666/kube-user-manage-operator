from typing import List, Dict, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
from webui_config import settings


class K8sClient:
    """Kubernetes 客户端封装"""
    
    def __init__(self):
        try:
            # 尝试加载集群内配置
            config.load_incluster_config()
        except:
            # 开发环境使用本地配置
            try:
                config.load_kube_config()
            except:
                raise Exception("无法加载 Kubernetes 配置")
        
        self.core_v1 = client.CoreV1Api()
        self.rbac_v1 = client.RbacAuthorizationV1Api()
        self.custom_api = client.CustomObjectsApi()
    
    # ==================== LensUser 管理 ====================
    
    def list_lensusers(self, namespace: str = "kube-system") -> List[Dict]:
        """列出所有 LensUser"""
        try:
            result = self.custom_api.list_namespaced_custom_object(
                group="osip.cc",
                version="v1",
                namespace=namespace,
                plural="lensuser"
            )
            return result.get("items", [])
        except ApiException as e:
            if e.status == 404:
                return []
            raise e
    
    def get_lensuser(self, name: str, namespace: str = "kube-system") -> Optional[Dict]:
        """获取单个 LensUser"""
        try:
            return self.custom_api.get_namespaced_custom_object(
                group="osip.cc",
                version="v1",
                namespace=namespace,
                plural="lensuser",
                name=name
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise e
    
    def create_lensuser(self, name: str, roles: List[Dict], namespace: str = "kube-system") -> Dict:
        """创建 LensUser"""
        body = {
            "apiVersion": "osip.cc/v1",
            "kind": "LensUser",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "roles": roles
            }
        }
        
        return self.custom_api.create_namespaced_custom_object(
            group="osip.cc",
            version="v1",
            namespace=namespace,
            plural="lensuser",
            body=body
        )
    
    def update_lensuser(self, name: str, roles: List[Dict], namespace: str = "kube-system") -> Dict:
        """更新 LensUser"""
        body = {
            "apiVersion": "osip.cc/v1",
            "kind": "LensUser",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "roles": roles
            }
        }
        
        return self.custom_api.replace_namespaced_custom_object(
            group="osip.cc",
            version="v1",
            namespace=namespace,
            plural="lensuser",
            name=name,
            body=body
        )
    
    def delete_lensuser(self, name: str, namespace: str = "kube-system") -> Dict:
        """删除 LensUser"""
        return self.custom_api.delete_namespaced_custom_object(
            group="osip.cc",
            version="v1",
            namespace=namespace,
            plural="lensuser",
            name=name
        )
    
    # ==================== ClusterRole 管理 ====================
    
    def list_managed_clusterroles(self) -> List[Dict]:
        """列出所有带 UserManager 标签的 ClusterRole"""
        try:
            label_selector = f"{settings.USER_MANAGER_LABEL}={settings.USER_MANAGER_LABEL_VALUE}"
            result = self.rbac_v1.list_cluster_role(label_selector=label_selector)
            
            roles = []
            for item in result.items:
                roles.append({
                    "name": item.metadata.name,
                    "labels": item.metadata.labels or {},
                    "rules": [self._rule_to_dict(rule) for rule in (item.rules or [])],
                    "creationTimestamp": item.metadata.creation_timestamp.isoformat() if item.metadata.creation_timestamp else None
                })
            return roles
        except ApiException as e:
            if e.status == 404:
                return []
            raise e
    
    def get_clusterrole(self, name: str) -> Optional[Dict]:
        """获取单个 ClusterRole"""
        try:
            role = self.rbac_v1.read_cluster_role(name)
            return {
                "name": role.metadata.name,
                "labels": role.metadata.labels or {},
                "rules": [self._rule_to_dict(rule) for rule in (role.rules or [])],
                "creationTimestamp": role.metadata.creation_timestamp.isoformat() if role.metadata.creation_timestamp else None
            }
        except ApiException as e:
            if e.status == 404:
                return None
            raise e
    
    def create_clusterrole(self, name: str, rules: List[Dict], description: str = "") -> Dict:
        """创建 ClusterRole"""
        labels = {
            settings.USER_MANAGER_LABEL: settings.USER_MANAGER_LABEL_VALUE
        }
        if description:
            labels["description"] = description
        
        body = client.V1ClusterRole(
            metadata=client.V1ObjectMeta(
                name=name,
                labels=labels
            ),
            rules=[self._dict_to_rule(rule) for rule in rules]
        )
        
        result = self.rbac_v1.create_cluster_role(body)
        return {
            "name": result.metadata.name,
            "labels": result.metadata.labels or {},
            "rules": rules
        }
    
    def update_clusterrole(self, name: str, rules: List[Dict], description: str = "") -> Dict:
        """更新 ClusterRole"""
        # 读取现有的 ClusterRole
        existing = self.rbac_v1.read_cluster_role(name)
        
        # 更新标签
        labels = existing.metadata.labels or {}
        labels[settings.USER_MANAGER_LABEL] = settings.USER_MANAGER_LABEL_VALUE
        if description:
            labels["description"] = description
        
        body = client.V1ClusterRole(
            metadata=client.V1ObjectMeta(
                name=name,
                labels=labels
            ),
            rules=[self._dict_to_rule(rule) for rule in rules]
        )
        
        result = self.rbac_v1.replace_cluster_role(name, body)
        return {
            "name": result.metadata.name,
            "labels": result.metadata.labels or {},
            "rules": rules
        }
    
    def delete_clusterrole(self, name: str) -> None:
        """删除 ClusterRole"""
        self.rbac_v1.delete_cluster_role(name)
    
    # ==================== Namespace 管理 ====================
    
    def list_namespaces(self) -> List[str]:
        """列出所有命名空间"""
        result = self.core_v1.list_namespace()
        return [item.metadata.name for item in result.items]
    
    # ==================== LuConfig 管理 ====================
    
    def get_luconfig(self, name: str, namespace: str = "kube-system") -> Optional[Dict]:
        """获取 LuConfig（包含 kubeconfig）"""
        try:
            return self.custom_api.get_namespaced_custom_object(
                group="osip.cc",
                version="v1",
                namespace=namespace,
                plural="luconfig",
                name=name
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise e
    
    # ==================== 辅助方法 ====================
    
    def _rule_to_dict(self, rule) -> Dict:
        """将 PolicyRule 转换为字典"""
        return {
            "apiGroups": rule.api_groups or [],
            "resources": rule.resources or [],
            "verbs": rule.verbs or [],
            "resourceNames": rule.resource_names or []
        }
    
    def _dict_to_rule(self, data: Dict):
        """将字典转换为 PolicyRule"""
        return client.V1PolicyRule(
            api_groups=data.get("apiGroups", []),
            resources=data.get("resources", []),
            verbs=data.get("verbs", []),
            resource_names=data.get("resourceNames", [])
        )


# 全局客户端实例
k8s_client = K8sClient()

