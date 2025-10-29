# Kube User Manage Operator

> 基于 Kubernetes Operator 的声明式用户权限管理系统

## 📖 项目介绍

Kube User Manage Operator 是一个基于 [Kopf](https://kopf.readthedocs.io/) 框架开发的 Kubernetes Operator，用于自动化管理集群用户访问权限。

### 核心功能

✅ **声明式管理**：通过 `LensUser` 自定义资源定义用户及权限  
✅ **自动化创建**：自动创建 ServiceAccount、RoleBinding、Token Secret  
✅ **Kubeconfig 生成**：自动生成 `LuConfig` CR，包含完整的 kubeconfig 配置  
✅ **版本兼容**：支持 Kubernetes 1.20+，兼容 1.24+ 的 Token 策略  
✅ **生命周期管理**：监听资源变更，自动同步权限配置  
✅ **Web 管理界面**：提供图形化界面管理用户和角色，支持账号密码登录  
✅ **标签过滤**：ClusterRole 通过标签管理，Web 界面只展示带有特定标签的角色  
✅ **CRD 自定义**：支持自定义 CRD 组名和版本，适配企业域名规范  
✅ **Helm 部署**：标准化 Helm Chart，一键部署完整系统

### 工作原理

```
创建 LensUser CR
      ↓
Operator 监听事件
      ↓
自动创建 ServiceAccount
      ↓
创建多个 RoleBinding (多命名空间)
      ↓
创建长期 Token Secret (K8s 1.24+)
      ↓
生成 LuConfig CR (包含 kubeconfig)
      ↓
用户获取配置访问集群
```

### 目录结构

```
.
├── image/                    # Operator 源码和镜像构建
│   ├── main.py              # 核心业务逻辑
│   ├── Dockerfile           # 容器镜像构建文件
│   ├── requirements.txt     # Python 依赖
│   ├── template/            # K8s 资源模板
│   └── example/             # 部署示例配置
├── lens-user/               # 部署清单文件
│   ├── 01-lensuser-crd.yaml.yaml          # LensUser CRD
│   ├── 02-lensuserconfig-crd.yaml         # LuConfig CRD
│   ├── 03-sa.yaml                         # Operator ServiceAccount
│   ├── 04-ClusterRoule-view-only.yaml     # 默认 ClusterRole
│   ├── 05-ClusterRoleBinding.yaml         # Operator 权限绑定
│   ├── 06-lensuser-deployment.yaml        # Operator 部署
│   └── 07-example.yaml                    # 用户示例
└── create-kubeconfig/       # 本地生成 kubeconfig 工具
    └── create-kubeconfig.py
```

---

## 🚀 部署方法

### 方式一：Helm 快速部署（推荐）⭐

使用 Helm Chart 一键部署完整系统（单镜像包含 Operator + Web UI）：

```bash
# 1. 构建镜像
docker build -t your-registry.com/kube-user-manage-operator:2.0.0 -f image/Dockerfile image/
docker push your-registry.com/kube-user-manage-operator:2.0.0

# 2. 安装
helm install kube-user-manager ./helm-chart \
  --namespace kube-system \
  --set operator.image.repository=your-registry.com/kube-user-manage-operator \
  --set operator.image.tag=2.0.0 \
  --set webui.auth.adminPassword=YourPassword \
  --set operator.cluster.name=your-cluster \
  --set operator.cluster.apiUrl=https://your-api-server:6443

# 3. 访问 Web 界面
kubectl port-forward -n kube-system svc/kube-user-manager 8080:8080
```

访问 http://localhost:8080，使用 admin/YourPassword 登录。

详细部署文档请参考：[DEPLOYMENT.md](DEPLOYMENT.md)

---

### 方式二：手动部署

#### 前置条件

- Kubernetes 1.20+ 集群
- kubectl 已配置并可访问集群
- 具有集群管理员权限
- Docker 或其他容器镜像构建工具（用于构建镜像）

### 第一步：部署基础资源

按顺序部署 CRD 和 RBAC 资源：

```bash
# 1. 部署 LensUser CRD
   kubectl apply -f lens-user/01-lensuser-crd.yaml.yaml

# 2. 部署 LuConfig CRD
   kubectl apply -f lens-user/02-lensuserconfig-crd.yaml

# 3. 部署 Operator ServiceAccount
   kubectl apply -f lens-user/03-sa.yaml

# 4. 部署默认 ClusterRole (view-only)
   kubectl apply -f lens-user/04-ClusterRoule-view-only.yaml

# 5. 部署 Operator ClusterRoleBinding
   kubectl apply -f lens-user/05-ClusterRoleBinding.yaml
   ```

或者一键部署基础资源：

```bash
kubectl apply -f lens-user/01-lensuser-crd.yaml.yaml \
              -f lens-user/02-lensuserconfig-crd.yaml \
              -f lens-user/03-sa.yaml \
              -f lens-user/04-ClusterRoule-view-only.yaml \
              -f lens-user/05-ClusterRoleBinding.yaml
```

### 第二步：构建并推送 Operator 镜像

```bash
# 构建镜像
docker build -t your-registry.com/kube-user-manage-operator:v1.0.0 -f image/Dockerfile image/

# 推送镜像到仓库
docker push your-registry.com/kube-user-manage-operator:v1.0.0
```

> **提示**：如果使用私有镜像仓库，需要先创建 imagePullSecret

### 第三步：配置并部署 Operator

编辑 `lens-user/06-lensuser-deployment.yaml`，修改以下配置：

```yaml
env:
  - name: cluster_name
    value: "your-cluster-name"        # 改为你的集群名称
  - name: kube_api_url
    value: "https://your-api-server:6443"  # 改为你的 API Server 地址
```

然后部署 Operator：

```bash
kubectl apply -f lens-user/06-lensuser-deployment.yaml
```

### 第四步：验证部署

检查 Operator 是否正常运行：

```bash
# 查看 Operator Pod 状态
kubectl get pods -n kube-system -l app=kube-user-manage-operator

# 查看 Operator 日志
kubectl logs -n kube-system -l app=kube-user-manage-operator -f

# 验证 CRD 是否创建成功（默认组名是 osip.cc，如自定义请替换）
kubectl get crd | grep osip.cc
# 或者如果自定义了 CRD 组名：
# kubectl get crd | grep your-domain.com
```

预期输出（默认配置）：
```
lensuser.osip.cc    2024-01-01T00:00:00Z
luconfig.osip.cc    2024-01-01T00:00:00Z
```

> 💡 **提示**：支持自定义 CRD 组名，详见 [CRD_CUSTOMIZATION.md](CRD_CUSTOMIZATION.md)

---

## 📝 使用方式

### 方式一：通过 Web 界面（推荐）🌐

1. **登录系统**
   - 访问 Web 界面（通过 Ingress 或 Port Forward）
   - 使用管理员账号登录（默认：admin/admin123）

2. **创建用户**
   - 点击"创建用户"按钮
   - 填写用户名（如：`john.doe`）
   - 选择命名空间（建议：`kube-system`）
   - 添加权限：
     - 选择角色（如：`view-only`）
     - 选择授权命名空间（如：`default`）
   - 点击"确定"

3. **下载 Kubeconfig**
   - 在用户列表中找到创建的用户
   - 点击"下载配置"按钮
   - 将下载的文件发送给用户

4. **管理角色**
   - 切换到"角色管理"标签
   - 点击"创建角色"创建自定义权限模板
   - 支持查看、编辑、删除角色
   - 只显示带有 `usermanager.{CRD_GROUP}/managed=true` 标签的角色（默认是 `usermanager.osip.cc/managed=true`）

---

### 方式二：通过 kubectl 命令行

#### 创建用户账号

#### 方式一：使用示例文件

```bash
# 应用示例配置
   kubectl apply -f lens-user/07-example.yaml
   ```

#### 方式二：自定义创建

创建一个 `my-user.yaml` 文件：

```yaml
# 注意：apiVersion 默认是 osip.cc/v1，如果自定义了 CRD_GROUP，请修改为 your-domain.com/v1
apiVersion: osip.cc/v1
kind: LensUser
metadata:
  name: john.doe              # 用户名
  namespace: kube-system      # 建议使用 kube-system
spec:
  roles:
    - name: admin             # ClusterRole 名称
      namespace: default      # 授权的命名空间
    - name: view-only         # ClusterRole 名称
      namespace: production   # 授权的命名空间
    - name: view-only
      namespace: staging
```

应用配置：

```bash
kubectl apply -f my-user.yaml
```

### 查看创建的资源

```bash
# 查看 LensUser
kubectl get lensuser -n kube-system

# 查看生成的 ServiceAccount
kubectl get sa john.doe -n kube-system

# 查看 RoleBinding
kubectl get rolebinding john.doe -n default
kubectl get rolebinding john.doe -n production

# 查看 Token Secret
kubectl get secret john.doe-token -n kube-system
```

### 获取 Kubeconfig

Operator 会自动生成 `LuConfig` CR，包含完整的 kubeconfig 信息：

```bash
# 查看 LuConfig
kubectl get luconfig john.doe -n kube-system -o yaml

# 提取 kubeconfig 内容
kubectl get luconfig john.doe -n kube-system -o jsonpath='{.spec}' | yq eval -P - > john.doe-kubeconfig.yaml
```

或使用本地工具生成：

```bash
cd create-kubeconfig
python create-kubeconfig.py john.doe 
```

生成的文件位于：`create-kubeconfig/output-kubeconfig/john.doe@cluster-name.yaml`

### 更新用户权限

编辑 LensUser 资源，修改 `spec.roles` 字段：

```bash
kubectl edit lensuser john.doe -n kube-system
```

或者修改 YAML 文件后重新应用：

```bash
kubectl apply -f my-user.yaml
```

Operator 会自动：
- 新增权限：创建新的 RoleBinding
- 删除权限：删除对应的 RoleBinding
- 修改权限：更新 RoleBinding 配置

### 删除用户账号

```bash
kubectl delete lensuser john.doe -n kube-system
```

Operator 会自动清理：
- ServiceAccount
- 所有 RoleBinding
- Token Secret
- LuConfig CR

---

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `cluster_name` | 集群名称，用于生成 kubeconfig context | `production-cluster` |
| `kube_api_url` | Kubernetes API Server 地址 | `https://10.0.0.1:6443` |

### ClusterRole 说明

项目默认提供 `view-only` ClusterRole，你可以使用任何已存在的 ClusterRole：

- `admin`：完整命名空间管理权限
- `edit`：编辑资源权限
- `view`：只读权限
- `view-only`：自定义只读权限（项目提供）

自定义 ClusterRole：

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: custom-role
rules:
  - apiGroups: [""]
    resources: ["pods", "services"]
    verbs: ["get", "list", "watch"]
```

---

## 🛠️ 本地开发

### 安装依赖

```bash
  pip install -r image/requirements.txt
  ```

### 本地运行 Operator

```bash
# 设置环境变量
export cluster_name=dev-cluster
export kube_api_url=https://127.0.0.1:6443

# 以开发模式运行
kopf run --dev --namespace kube-system image/main.py
```

### 构建镜像

```bash
docker build -t kube-user-manage-operator:dev -f image/Dockerfile image/
```

---

## ❓ 常见问题

### Q1: Operator Pod 启动失败

**解决方法**：
```bash
# 检查日志
kubectl logs -n kube-system -l app=kube-user-manage-operator

# 确认 RBAC 权限是否正确
kubectl auth can-i create serviceaccounts --as=system:serviceaccount:kube-system:kube-user-manage-operator
```

### Q2: ServiceAccount 没有生成 Token Secret

这是 Kubernetes 1.24+ 的正常行为，Operator 会自动创建永久 Token Secret。

**验证**：
```bash
kubectl get secret <username>-token -n kube-system
```

### Q3: RoleBinding 创建失败

**原因**：ClusterRole 不存在

**解决方法**：
```bash
# 检查 ClusterRole 是否存在
kubectl get clusterrole <role-name>

# 如果不存在，创建对应的 ClusterRole
kubectl apply -f lens-user/04-ClusterRoule-view-only.yaml
```

### Q4: 如何获取 API Server 地址

```bash
kubectl cluster-info | grep "Kubernetes control plane"
```

### Q5: 如何查看 Operator 版本

```bash
kubectl get deployment kube-user-manage-operator -n kube-system -o jsonpath='{.spec.template.spec.containers[0].image}'
```

---

## 📋 完整示例

以下是一个完整的用户创建流程示例：

```bash
# 1. 创建用户配置文件
# 注意：apiVersion 默认是 osip.cc/v1，如自定义了 CRD_GROUP，请修改为 your-domain.com/v1
cat <<EOF > developer-user.yaml
apiVersion: osip.cc/v1
kind: LensUser
metadata:
  name: developer
  namespace: kube-system
spec:
  roles:
    - name: edit
      namespace: dev
    - name: view
      namespace: prod
EOF

# 2. 应用配置
kubectl apply -f developer-user.yaml

# 3. 等待资源创建（通常几秒钟）
sleep 5

# 4. 验证资源
kubectl get lensuser developer -n kube-system
kubectl get sa developer -n kube-system
kubectl get rolebinding developer -n dev
kubectl get rolebinding developer -n prod

# 5. 获取 kubeconfig
kubectl get luconfig developer -n kube-system -o yaml

# 6. 导出为文件
kubectl get luconfig developer -n kube-system -o jsonpath='{.spec}' | \
  python -c "import sys, yaml; print(yaml.dump(yaml.safe_load(sys.stdin.read())))" > developer.kubeconfig

# 7. 测试访问
kubectl --kubeconfig=developer.kubeconfig get pods -n dev
```

---

## 📚 更多资源

- [Kopf 官方文档](https://kopf.readthedocs.io/)
- [Kubernetes Operator 最佳实践](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/)
- [RBAC 权限管理](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

---

## 📄 许可证

**Apache-2.0**
