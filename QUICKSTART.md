# 🚀 快速开始指南

## 5 分钟上手

### 第一步：构建镜像

```bash
# 构建 Operator 镜像
docker build -t your-registry.com/kube-user-manage-operator:2.0.0 -f image/Dockerfile image/

# 构建 Web UI 镜像
docker build -t your-registry.com/kube-user-manager-webui:2.0.0 -f webui/Dockerfile webui/

# 推送镜像
docker push your-registry.com/kube-user-manage-operator:2.0.0
docker push your-registry.com/kube-user-manager-webui:2.0.0
```

### 第二步：配置并部署

```bash
# 修改配置
cat > my-values.yaml <<EOF
operator:
  image:
    repository: your-registry.com/kube-user-manage-operator
    tag: "2.0.0"
  cluster:
    name: "my-cluster"
    apiUrl: "https://10.0.0.1:6443"

webui:
  image:
    repository: your-registry.com/kube-user-manager-webui
    tag: "2.0.0"
  auth:
    secretKey: "my-super-secret-key-32-chars-long"
    adminPassword: "MySecurePassword123!"

ingress:
  enabled: false
EOF

# 使用 Helm 安装
helm install kube-user-manager ./helm-chart \
  --namespace kube-system \
  --values my-values.yaml
```

### 第三步：访问 Web 界面

```bash
# Port Forward
kubectl port-forward -n kube-system svc/kube-user-manager-webui 8080:8080
```

访问 http://localhost:8080

- 用户名：`admin`
- 密码：`MySecurePassword123!`

### 第四步：创建第一个用户

#### 通过 Web 界面：

1. 登录后点击"创建用户"
2. 填写信息：
   - 用户名：`developer`
   - 命名空间：`kube-system`
   - 权限：`view-only` @ `default`
3. 点击确定
4. 等待几秒后点击"下载配置"

#### 通过命令行：

```bash
cat <<EOF | kubectl apply -f -
apiVersion: osip.cc/v1
kind: LensUser
metadata:
  name: developer
  namespace: kube-system
spec:
  roles:
    - name: view-only
      namespace: default
EOF

# 等待资源创建
sleep 5

# 下载 kubeconfig
kubectl get luconfig developer -n kube-system -o jsonpath='{.spec}' > developer-kubeconfig.yaml
```

### 第五步：测试用户权限

```bash
# 使用下载的 kubeconfig
kubectl --kubeconfig=developer-kubeconfig.yaml get pods -n default

# 应该能看到 pods（只读权限）
kubectl --kubeconfig=developer-kubeconfig.yaml get pods -n default

# 应该无法创建资源
kubectl --kubeconfig=developer-kubeconfig.yaml create deployment test --image=nginx -n default
# Error: forbidden
```

---

## 🎯 下一步

- 📖 查看完整文档：[README.md](README.md)
- 🚀 详细部署指南：[DEPLOYMENT.md](DEPLOYMENT.md)
- 🔧 自定义 ClusterRole
- 🌐 启用 Ingress 配置域名访问
- 🔐 集成企业 SSO/LDAP（待实现）

---

## 💡 常见操作

### 创建自定义角色

```bash
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-custom-role
  labels:
    usermanager.osip.cc/managed: "true"
    description: "自定义开发角色"
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch", "create", "update"]
EOF
```

### 更新用户权限

```bash
kubectl edit lensuser developer -n kube-system

# 或使用 Web 界面编辑
```

### 查看所有用户

```bash
kubectl get lensuser -n kube-system
```

### 查看用户的 kubeconfig

```bash
kubectl get luconfig developer -n kube-system -o yaml
```

---

## ⚠️ 注意事项

1. **安全**：生产环境务必修改默认密码
2. **备份**：重要数据（CRD）做好备份
3. **权限**：谨慎授予 `admin` 等高权限角色
4. **标签**：创建的 ClusterRole 必须带有 `usermanager.osip.cc/managed=true` 标签才能在 Web 界面显示

---

## 🆘 遇到问题？

```bash
# 查看 Operator 日志
kubectl logs -n kube-system -l app.kubernetes.io/component=operator

# 查看 Web UI 日志
kubectl logs -n kube-system -l app.kubernetes.io/component=webui

# 查看所有资源
kubectl get all -n kube-system -l app.kubernetes.io/name=kube-user-manager
```

更多帮助请查看 [DEPLOYMENT.md](DEPLOYMENT.md) 的故障排查部分。

