# 完全卸载指南

## 📝 概述

本指南提供了完全清理 Kube User Manager 的所有资源的步骤，包括：
- Operator 部署
- Web UI 服务
- CRD 定义
- 创建的用户资源
- RBAC 权限
- ServiceAccount

---

## 🚀 快速清理（推荐）

### 方法一：Helm 一键卸载

如果您使用 Helm 部署的：

```bash
# 1. 卸载 Helm Release
helm uninstall kube-user-manager -n kube-system

# 2. 删除所有 LensUser 资源（防止 finalizer 阻塞）
kubectl delete lensuser --all -A --force --grace-period=0

# 3. 删除所有 LuConfig 资源
kubectl delete luconfig --all -A --force --grace-period=0

# 4. 删除 CRD（会级联删除所有相关资源）
kubectl delete crd lensuser.osip.cc
kubectl delete crd luconfig.osip.cc
# 如果自定义了 CRD 组名，替换为：
# kubectl delete crd lensuser.your-domain.com
# kubectl delete crd luconfig.your-domain.com

# 5. 删除管理的 ClusterRole（可选）
kubectl delete clusterrole -l usermanager.osip.cc/managed=true
# 如果自定义了 CRD 组名，替换为：
# kubectl delete clusterrole -l usermanager.your-domain.com/managed=true
```

---

## 🔧 详细清理步骤

### 1. 删除所有 LensUser 资源

**重要**：先删除用户资源，Operator 会自动清理关联的 ServiceAccount、RoleBinding 和 LuConfig。

```bash
# 查看所有 LensUser
kubectl get lensuser -A

# 删除所有 LensUser（Operator 会自动清理相关资源）
kubectl delete lensuser --all --all-namespaces

# 如果删除卡住（有 finalizer），强制删除：
kubectl delete lensuser --all -A --force --grace-period=0
```

### 2. 删除所有 LuConfig 资源

```bash
# 查看所有 LuConfig
kubectl get luconfig -A

# 删除所有 LuConfig
kubectl delete luconfig --all --all-namespaces --force --grace-period=0
```

### 3. 卸载 Operator

#### 如果使用 Helm 部署：

```bash
# 卸载 Release
helm uninstall kube-user-manager -n kube-system

# 验证 Pod 是否已删除
kubectl get pods -n kube-system -l app=kube-user-manager
```

#### 如果手动部署：

```bash
# 删除 Deployment
kubectl delete deployment kube-user-manager -n kube-system

# 删除 Service
kubectl delete service kube-user-manager -n kube-system

# 删除 ServiceAccount
kubectl delete serviceaccount kube-user-manager -n kube-system

# 删除 RBAC
kubectl delete clusterrolebinding kube-user-manager
kubectl delete clusterrole kube-user-manager
```

### 4. 删除 CRD

**警告**：删除 CRD 会级联删除所有该类型的资源！

```bash
# 查看 CRD
kubectl get crd | grep osip.cc
# 或者如果自定义了组名：
# kubectl get crd | grep your-domain.com

# 删除 CRD
kubectl delete crd lensuser.osip.cc
kubectl delete crd luconfig.osip.cc

# 如果自定义了 CRD 组名，替换为：
# kubectl delete crd lensuser.your-domain.com
# kubectl delete crd luconfig.your-domain.com
```

### 5. 清理残留的 ServiceAccount 和 RoleBinding

如果 Operator 没有正确清理，手动清理残留资源：

```bash
# 查找所有可能残留的 ServiceAccount
# 这些通常与 LensUser 同名
kubectl get sa -A | grep -E "test-user|developer|your-user-pattern"

# 手动删除残留的 ServiceAccount（替换为实际的名称和命名空间）
kubectl delete sa <service-account-name> -n <namespace>

# 查找残留的 RoleBinding
kubectl get rolebinding -A | grep -E "test-user|developer"

# 删除残留的 RoleBinding
kubectl delete rolebinding <rolebinding-name> -n <namespace>

# 查找残留的 Token Secret
kubectl get secret -A | grep token

# 删除残留的 Token Secret
kubectl delete secret <secret-name> -n <namespace>
```

### 6. 清理默认 ClusterRole

如果您想删除系统创建的默认角色：

```bash
# 删除所有带有管理标签的 ClusterRole
kubectl delete clusterrole -l usermanager.osip.cc/managed=true

# 如果自定义了 CRD 组名：
# kubectl delete clusterrole -l usermanager.your-domain.com/managed=true

# 或者手动删除特定角色：
kubectl delete clusterrole view-only
```

### 7. 删除 Ingress（如果配置了）

```bash
# 查看 Ingress
kubectl get ingress -n kube-system

# 删除 Ingress
kubectl delete ingress kube-user-manager -n kube-system
```

---

## 🔍 验证清理完成

运行以下命令确认所有资源已删除：

```bash
# 1. 检查 CRD
kubectl get crd | grep -E "lensuser|luconfig"
# 预期：无输出

# 2. 检查 LensUser 资源
kubectl get lensuser -A
# 预期：No resources found

# 3. 检查 LuConfig 资源
kubectl get luconfig -A
# 预期：No resources found

# 4. 检查 Deployment
kubectl get deployment kube-user-manager -n kube-system
# 预期：Error from server (NotFound)

# 5. 检查 Service
kubectl get service kube-user-manager -n kube-system
# 预期：Error from server (NotFound)

# 6. 检查 ServiceAccount
kubectl get sa kube-user-manager -n kube-system
# 预期：Error from server (NotFound)

# 7. 检查 RBAC
kubectl get clusterrole kube-user-manager
kubectl get clusterrolebinding kube-user-manager
# 预期：Error from server (NotFound)

# 8. 检查管理的 ClusterRole
kubectl get clusterrole -l usermanager.osip.cc/managed=true
# 预期：No resources found
```

---

## 🛑 故障排查

### 问题 1：CRD 删除卡住

**原因**：有资源被 finalizer 保护

**解决方案**：

```bash
# 1. 查看被卡住的资源
kubectl get lensuser -A -o json | jq '.items[] | select(.metadata.deletionTimestamp != null)'

# 2. 移除 finalizer
kubectl patch lensuser <name> -n <namespace> -p '{"metadata":{"finalizers":[]}}' --type=merge

# 3. 强制删除 CRD
kubectl delete crd lensuser.osip.cc --force --grace-period=0
```

### 问题 2：Namespace 卡在 Terminating 状态

**原因**：有资源没有正确清理

**解决方案**：

```bash
# 查看 namespace 中的资源
kubectl api-resources --verbs=list --namespaced -o name | xargs -n 1 kubectl get --show-kind --ignore-not-found -n <namespace>

# 强制删除 namespace
kubectl get namespace <namespace> -o json | jq '.spec.finalizers = []' | kubectl replace --raw "/api/v1/namespaces/<namespace>/finalize" -f -
```

### 问题 3：找不到特定组名的 CRD

**解决方案**：

```bash
# 查看所有 CRD
kubectl get crd

# 使用通配符查找
kubectl get crd | grep lensuser
kubectl get crd | grep luconfig

# 删除找到的 CRD
kubectl delete crd <crd-full-name>
```

---

## 📦 清理脚本

使用提供的清理脚本一键清理：

```bash
# 赋予执行权限
chmod +x cleanup.sh

# 执行清理（默认组名 osip.cc）
./cleanup.sh

# 自定义 CRD 组名
./cleanup.sh --crd-group your-domain.com
```

---

## ⚠️ 注意事项

1. **备份重要数据**：删除前请确保已导出重要的用户 kubeconfig
2. **生产环境**：在生产环境操作前请做好备份和测试
3. **CRD 删除**：删除 CRD 会立即删除所有该类型的资源，不可恢复
4. **用户访问**：删除后，所有使用这些 kubeconfig 的用户将无法访问集群
5. **ServiceAccount**：删除会同时删除关联的 Token，立即生效

---

## 🔄 重新安装

清理完成后，如需重新安装：

```bash
# 使用 Helm 重新安装
helm install kube-user-manager ./helm-chart \
  --namespace kube-system \
  --set operator.image.tag=v1.19 \
  --set webui.auth.adminPassword=NewPassword
```

---

## 📚 相关文档

- [安装文档](README.md)
- [CRD 自定义说明](CRD_CUSTOMIZATION.md)
- [故障排查](TROUBLESHOOTING.md)

