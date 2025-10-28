Kube User Manage Operator
==========================

Kube User Manage Operator 是一个基于 [Kopf](https://kopf.readthedocs.io/) 的 Kubernetes Operator，用于在集群内以声明式方式管理 Lens/开发者的访问账号和权限。通过自定义资源 `LensUser`，Operator 会自动完成 ServiceAccount 创建、角色绑定、长期 token Secret 生成，并把 kubeconfig 以 `LuConfig` CR 的形式输出，简化账号发放流程。

目录结构
--------
- `image/`  
  Operator 的源码、镜像构建文件以及模板资源。
- `lens-user/`  
  手动部署所需的 Kubernetes 清单（CRD、ClusterRole、Deployment、示例 CR 等）。
- `create-kubeconfig/`  
  本地辅助脚本，基于模板为指定 ServiceAccount 输出 kubeconfig。

核心特性
--------
- **自动注册 CRD**：Operator 启动时会确保 `lensuser.garena.com` 与 `luconfig.garena.com` 两个 CRD 已存在。
- **账号生命周期管理**：监听 `LensUser` 创建/更新/删除事件，自动同步 ServiceAccount、RoleBinding 以及 `LuConfig`。
- **Token 兼容性处理**：兼容 Kubernetes 1.24+ 及以上版本，若集群未自动生成长期 token Secret 会自动补齐并绑定。
- **声明式 kubeconfig 输出**：为每个 `LensUser` 生成 `LuConfig` CR，包含 base64 CA、Bearer Token 等信息，便于外部系统消费。
- **模板灵活复用**：所有 YAML 模板集中在 `image/template/`，方便按需扩展 `ClusterRole`、`RoleBinding` 等定义。

快速开始
--------
1. **准备环境**
   - Kubernetes 1.20+ 集群（若启用了 LegacyServiceAccountTokenNoAutoGeneration，需要允许手动创建 token Secret）。。
   - 管理权限账号（用于部署 CRD/ClusterRole/Deployment）。
   - `kubectl`、`docker`/`nerdctl` 等镜像构建工具。

2. **部署基础资源**（可直接使用 `lens-user/` 目录提供的清单）：
   ```powershell
   kubectl apply -f lens-user/01-lensuser-crd.yaml.yaml
   kubectl apply -f lens-user/02-lensuserconfig-crd.yaml
   kubectl apply -f lens-user/03-sa.yaml
   kubectl apply -f lens-user/04-ClusterRoule-view-only.yaml
   kubectl apply -f lens-user/05-ClusterRoleBinding.yaml
   ```

3. **构建 Operator 镜像**：
   ```powershell
   docker build -t <your-registry>/kube-user-manage-operator:latest -f image/Dockerfile image
   docker push <your-registry>/kube-user-manage-operator:latest
   ```

4. **部署 Operator**：
   - 修改 `image/example/deployment.yaml` 中的 `image`, `cluster_name`, `kube_api_url` 等环境变量。
   - 应用部署：
     ```powershell
     kubectl apply -f image/example/deployment.yaml
     ```
   > 若需要多个副本运行，请确保 Kopf peering 的 RBAC 和网络访问正常。

5. **创建示例 LensUser**：
   ```powershell
   kubectl apply -f lens-user/07-example.yaml
   ```
   Operator 会自动创建 `kube-system` namespace 下的 ServiceAccount `test.user`、相关 RoleBinding，并生成 `LuConfig`：
   ```powershell
   kubectl get luconfig test.user -n kube-system -o yaml
   ```

环境变量与配置
--------------
- `cluster_name`：写入 `LuConfig` 中 context 名称，通常使用集群别名。
- `kube_api_url`：写入 kubeconfig 中的 API Server 地址。
- 模板文件位于 `image/template/`，可根据企业需求扩展或替换：  
  - `cluster-role.yaml`：默认 `view-only` 权限。  
  - `rolebinding.yaml`：为每个 namespace 创建 `ClusterRole` 绑定。  
  - `secret.yaml`、`kube-config.yaml`：定义 token Secret 与 `LuConfig` 输出格式。

LensUser CR 示例
---------------
```yaml
apiVersion: garena.com/v1
kind: LensUser
metadata:
  name: test.user
  namespace: kube-system
spec:
  roles:
    - name: admin
      namespace: default
    - name: view-only
      namespace: kube-system
```
- `spec.roles` 为数组，`name` 对应 `ClusterRole` 名称，`namespace` 为 RoleBinding 创建位置。
- CR 更新时，Operator 会自动新增/删除/替换对应的 RoleBinding。

本地生成 kubeconfig
------------------
`create-kubeconfig/` 目录提供了一个简单脚本，可针对已有 ServiceAccount 生成 kubeconfig：
```powershell
cd create-kubeconfig
python create-kubeconfig.py <service-account-name>
```
流程说明：
1. 根据 `init-conf/init-secret.yaml` 模板创建 token Secret。
2. 调用 `kubectl get secret` 获取 token，并填充 `init-conf/init-kubeconfig.yaml` 模板。
3. 在终端打印 kubeconfig，并写入 `output-kubeconfig/<context>.yaml`。

开发与测试
----------
- 依赖见 `image/requirements.txt`，建议使用 Python 3.7+ 虚拟环境：
  ```powershell
  pip install -r image/requirements.txt
  ```
- 开发时可通过 `kopf run --dev --namespace kube-system image/main.py` 在本地连接集群调试。
- 修改模板后记得更新镜像并重新部署。

常见问题
--------
- **CRD 冲突**：Operator 启动会先读取现有 CRD，若已存在会记录日志并跳过创建。确保版本兼容即可。  
- **ServiceAccount 未生成 token Secret**：对于 1.24+，Operator 会手动创建 `<sa>-token` Secret；若失败请检查 `kube-system` namespace 是否允许创建 `kubernetes.io/service-account-token` 类型 Secret。  
- **RoleBinding 权限不足**：确保 `roleRef.name` 对应的 ClusterRole 已存在，如需自定义请更新模板或部署新的 ClusterRole。

路线图
------
- 支持为不同角色绑定指定 `ClusterRole` 模板。
- 提供 Helm Chart 简化部署流程。
- 增加单元测试与 CI 发布流程。

许可证
------
目前尚未添加许可协议，请在对外发布前根据企业策略补充（例如 MIT、Apache-2.0 等）。
