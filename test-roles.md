# 角色管理问题排查步骤

## 问题现象
角色管理页面显示 "-"，没有角色名称和描述

## 可能原因
1. 后端只返回带 `usermanager.osip.cc/managed=true` 标签的 ClusterRole
2. 你创建的角色可能没有这个标签

## 验证步骤

### 1. 检查后端是否有数据返回
打开浏览器控制台（F12），切换到 Network 标签，刷新页面，查看：
- `/api/clusterroles` 请求的响应内容
- 是否返回了 `{"success": true, "data": [...]}`

### 2. 检查 K8s 中的角色
```bash
# 查看所有 ClusterRole
kubectl get clusterrole

# 查看带标签的 ClusterRole
kubectl get clusterrole -l usermanager.osip.cc/managed=true

# 查看具体角色的标签
kubectl get clusterrole view-only -o yaml | grep -A 5 labels
```

### 3. 给现有角色添加标签
```bash
# 给 view-only 角色添加管理标签
kubectl label clusterrole view-only usermanager.osip.cc/managed=true

# 或者手动编辑
kubectl edit clusterrole view-only
# 添加：
# metadata:
#   labels:
#     usermanager.osip.cc/managed: "true"
```

## 快速修复

### 方案 1：通过 WebUI 重新创建角色
删除旧角色，通过 WebUI 重新创建，会自动添加标签

### 方案 2：手动添加标签到现有角色
```bash
kubectl label clusterrole view-only usermanager.osip.cc/managed=true
kubectl label clusterrole admin usermanager.osip.cc/managed=true
# ... 对其他角色重复
```

### 方案 3：修改后端不过滤标签（不推荐）
如果想显示所有 ClusterRole，修改 `image/webui_k8s.py`:
```python
def list_managed_clusterroles(self) -> List[Dict]:
    """列出所有 ClusterRole"""
    try:
        # 注释掉标签过滤
        # label_selector = f"{settings.USER_MANAGER_LABEL}={settings.USER_MANAGER_LABEL_VALUE}"
        result = self.rbac_v1.list_cluster_role()  # 不传 label_selector
        # ...
```

## 验证修复
1. 刷新页面，角色列表应该显示正常
2. 创建新角色，自动添加标签
3. 编辑角色，保持标签

