# 部署文档

## 📦 Helm 快速部署指南

### 前置条件

- Kubernetes 1.20+ 集群
- Helm 3.x
- kubectl 配置并可访问集群
- 具有集群管理员权限

---

## 🚀 快速开始

### 1. 构建镜像

#### 构建 Operator 镜像

```bash
cd image
docker build -t your-registry.com/kube-user-manage-operator:2.0.0 -f Dockerfile .
docker push your-registry.com/kube-user-manage-operator:2.0.0
```

#### 构建 Web UI 镜像

```bash
cd webui
docker build -t your-registry.com/kube-user-manager-webui:2.0.0 -f Dockerfile .
docker push your-registry.com/kube-user-manager-webui:2.0.0
```

### 2. 配置 Helm Values

编辑 `helm-chart/values.yaml` 文件：

```yaml
# 修改镜像仓库地址
operator:
  image:
    repository: your-registry.com/kube-user-manage-operator
    tag: "2.0.0"
  
  cluster:
    name: "your-cluster-name"
    apiUrl: "https://your-api-server:6443"

webui:
  image:
    repository: your-registry.com/kube-user-manager-webui
    tag: "2.0.0"
  
  # ⚠️ 生产环境务必修改管理员密码！
  auth:
    secretKey: "your-random-secret-key-at-least-32-chars"
    adminUsername: "admin"
    adminPassword: "your-secure-password"

# 启用 Ingress（可选）
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: kube-user-manager.example.com
      paths:
        - path: /
          pathType: Prefix
```

### 3. 安装 Helm Chart

```bash
# 安装
helm install kube-user-manager ./helm-chart \
  --namespace kube-system \
  --create-namespace

# 或使用自定义配置
helm install kube-user-manager ./helm-chart \
  --namespace kube-system \
  --set webui.auth.adminPassword=YourSecurePassword \
  --set operator.cluster.name=production \
  --set operator.cluster.apiUrl=https://10.0.0.1:6443
```

### 4. 验证部署

```bash
# 检查 Pod 状态
kubectl get pods -n kube-system -l app.kubernetes.io/name=kube-user-manager

# 检查 CRD
kubectl get crd | grep osip.cc

# 检查 Service
kubectl get svc -n kube-system -l app.kubernetes.io/name=kube-user-manager

# 查看日志
kubectl logs -n kube-system -l app.kubernetes.io/component=operator
kubectl logs -n kube-system -l app.kubernetes.io/component=webui
```

预期输出：
```
NAME                                        READY   STATUS    RESTARTS   AGE
kube-user-manager-operator-xxx-xxx          1/1     Running   0          1m
kube-user-manager-webui-xxx-xxx             1/1     Running   0          1m
```

### 5. 访问 Web 界面

#### 方式一：通过 Port Forward（开发环境）

```bash
kubectl port-forward -n kube-system svc/kube-user-manager-webui 8080:8080
```

访问 http://localhost:8080

#### 方式二：通过 Ingress（生产环境）

如果启用了 Ingress，访问配置的域名：http://kube-user-manager.example.com

#### 方式三：通过 NodePort

修改 `values.yaml`：

```yaml
webui:
  service:
    type: NodePort
```

然后获取 NodePort：

```bash
kubectl get svc -n kube-system kube-user-manager-webui
```

访问 http://node-ip:node-port

---

## 🔐 初次登录

默认管理员账号：
- 用户名：`admin`
- 密码：`admin123`（如果没有修改 values.yaml）

**⚠️ 警告：生产环境必须修改默认密码！**

---

## 📝 使用示例

### 创建用户

1. 登录 Web 界面
2. 点击"创建用户"
3. 填写：
   - 用户名：`developer`
   - 命名空间：`kube-system`
   - 权限：选择 `view-only` @ `default`
4. 点击"确定"

### 创建自定义角色

1. 切换到"角色管理"
2. 点击"创建角色"
3. 填写：
   - 角色名称：`my-custom-role`
   - 描述：`自定义角色`
   - 添加权限规则：
     - API Groups: `apps`
     - Resources: `deployments`
     - Verbs: `get, list, watch`
4. 点击"确定"

### 下载用户 Kubeconfig

1. 在用户列表中找到目标用户
2. 点击"下载配置"
3. 保存为 `username-kubeconfig.yaml`
4. 使用：`kubectl --kubeconfig=username-kubeconfig.yaml get pods`

---

## 🔧 配置说明

### Operator 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `operator.enabled` | 是否启用 Operator | `true` |
| `operator.replicas` | 副本数 | `1` |
| `operator.image.repository` | Operator 镜像仓库 | - |
| `operator.image.tag` | Operator 镜像标签 | `2.0.0` |
| `operator.cluster.name` | 集群名称 | `kubernetes` |
| `operator.cluster.apiUrl` | API Server 地址 | `https://kubernetes.default.svc` |

### Web UI 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `webui.enabled` | 是否启用 Web UI | `true` |
| `webui.replicas` | 副本数 | `1` |
| `webui.image.repository` | Web UI 镜像仓库 | - |
| `webui.image.tag` | Web UI 镜像标签 | `2.0.0` |
| `webui.auth.adminUsername` | 管理员用户名 | `admin` |
| `webui.auth.adminPassword` | 管理员密码 | `admin123` |
| `webui.service.type` | Service 类型 | `ClusterIP` |
| `webui.service.port` | Service 端口 | `8080` |

### Ingress 配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `ingress.enabled` | 是否启用 Ingress | `false` |
| `ingress.className` | Ingress Class | `nginx` |
| `ingress.hosts[0].host` | 域名 | `kube-user-manager.example.com` |

---

## 🔄 升级

```bash
# 升级到新版本
helm upgrade kube-user-manager ./helm-chart \
  --namespace kube-system \
  --set webui.auth.adminPassword=YourPassword

# 查看升级历史
helm history kube-user-manager -n kube-system

# 回滚到上一个版本
helm rollback kube-user-manager -n kube-system
```

---

## 🗑️ 卸载

```bash
# 卸载 Helm Release
helm uninstall kube-user-manager -n kube-system

# 如果需要删除 CRD（会删除所有 LensUser 和 LuConfig）
kubectl delete crd lensuser.osip.cc
kubectl delete crd luconfig.osip.cc

# 删除带标签的 ClusterRole（可选）
kubectl delete clusterrole -l usermanager.osip.cc/managed=true
```

---

## 🛠️ 故障排查

### Operator Pod 启动失败

```bash
# 查看日志
kubectl logs -n kube-system -l app.kubernetes.io/component=operator

# 常见问题：
# 1. RBAC 权限不足
kubectl auth can-i create serviceaccounts --as=system:serviceaccount:kube-system:kube-user-manager

# 2. CRD 未创建
kubectl get crd | grep osip.cc
```

### Web UI 无法访问

```bash
# 检查 Pod 状态
kubectl get pods -n kube-system -l app.kubernetes.io/component=webui

# 检查 Service
kubectl get svc -n kube-system kube-user-manager-webui

# 检查日志
kubectl logs -n kube-system -l app.kubernetes.io/component=webui

# 测试连接
kubectl port-forward -n kube-system svc/kube-user-manager-webui 8080:8080
```

### 登录失败

检查环境变量是否正确设置：

```bash
kubectl get deployment -n kube-system kube-user-manager-webui -o jsonpath='{.spec.template.spec.containers[0].env}'
```

---

## 🔒 安全建议

1. **修改默认密码**：
   ```bash
   helm upgrade kube-user-manager ./helm-chart \
     --namespace kube-system \
     --set webui.auth.adminPassword='YourStrongPassword123!'
   ```

2. **使用 Secret 存储密码**：
   
   创建 Secret：
   ```bash
   kubectl create secret generic webui-auth \
     --from-literal=admin-password='YourStrongPassword' \
     -n kube-system
   ```
   
   修改 Deployment 使用 Secret（需要自定义 Helm templates）

3. **启用 HTTPS**：
   ```yaml
   ingress:
     enabled: true
     annotations:
       cert-manager.io/cluster-issuer: letsencrypt-prod
     tls:
       - secretName: kube-user-manager-tls
         hosts:
           - kube-user-manager.example.com
   ```

4. **限制访问 IP**：
   ```yaml
   ingress:
     annotations:
       nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8,192.168.0.0/16"
   ```

---

## 📊 监控

### Prometheus 指标（待实现）

```yaml
# ServiceMonitor 示例
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: kube-user-manager
  namespace: kube-system
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: kube-user-manager
  endpoints:
    - port: metrics
```

---

## 🆘 获取帮助

如有问题，请：

1. 查看日志：`kubectl logs -n kube-system -l app.kubernetes.io/name=kube-user-manager`
2. 检查事件：`kubectl get events -n kube-system --sort-by='.lastTimestamp'`
3. 提交 Issue：https://github.com/yourusername/kube-user-manage-operator/issues

---

## 📚 相关文档

- [README.md](README.md) - 项目介绍
- [Helm 官方文档](https://helm.sh/docs/)
- [Kubernetes Operator 最佳实践](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)

