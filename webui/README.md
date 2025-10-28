# Web UI 说明

## 架构

```
webui/
├── backend/           # FastAPI 后端
│   ├── app.py        # 主应用
│   ├── auth.py       # JWT 认证
│   ├── k8s_client.py # Kubernetes 客户端
│   ├── config.py     # 配置管理
│   └── requirements.txt
├── frontend/          # Vue 3 前端
│   ├── index.html    # 主页面
│   ├── app.js        # Vue 应用
│   └── style.css     # 样式
└── Dockerfile        # 容器镜像
```

## 技术栈

### 后端
- **FastAPI**: 现代化的 Python Web 框架
- **JWT**: 用户认证
- **kubernetes-client**: K8s API 交互

### 前端
- **Vue 3**: 渐进式 JavaScript 框架
- **Element Plus**: UI 组件库
- **js-yaml**: YAML 处理

## 本地开发

### 启动后端

```bash
cd webui/backend

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin123
export SECRET_KEY=your-secret-key
export CLUSTER_NAME=dev-cluster
export KUBE_API_URL=https://kubernetes.default.svc

# 启动服务
python app.py
```

访问 http://localhost:8080

### 开发前端

前端使用 CDN 加载依赖，无需构建步骤。

修改文件后刷新浏览器即可。

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SECRET_KEY` | JWT 密钥 | `your-secret-key-change-in-production` |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `CLUSTER_NAME` | 集群名称 | `kubernetes` |
| `KUBE_API_URL` | API Server 地址 | `https://kubernetes.default.svc` |

## ClusterRole 标签

Web 界面只显示带有以下标签的 ClusterRole：

```yaml
labels:
  usermanager.osip.cc/managed: "true"
```

创建 ClusterRole 示例：

```bash
kubectl create clusterrole my-role \
  --verb=get,list,watch \
  --resource=pods,services

kubectl label clusterrole my-role usermanager.osip.cc/managed=true
```

## 功能特性

### 用户管理
- ✅ 列表展示
- ✅ 创建用户
- ✅ 编辑用户（更新权限）
- ✅ 删除用户
- ✅ 下载 Kubeconfig

### 角色管理
- ✅ 列表展示（仅显示带标签的）
- ✅ 创建角色
- ✅ 编辑角色
- ✅ 查看详情
- ✅ 删除角色

### 安全特性
- ✅ JWT Token 认证
- ✅ Token 24小时过期
- ✅ 自动登出
- ✅ CORS 配置

## 扩展开发

### 添加新的 API 端点

在 `backend/app.py` 中添加：

```python
@app.get("/api/custom", tags=["自定义"])
async def custom_endpoint(current_user: User = Depends(get_current_user)):
    return {"message": "自定义功能"}
```

### 添加新的前端页面

在 `frontend/index.html` 中添加菜单项和页面内容。

### 集成数据库

当前使用简单的内存存储。如需持久化用户数据，可以集成：
- PostgreSQL
- MySQL
- MongoDB

修改 `backend/auth.py` 中的 `authenticate_user` 函数。

## 部署

使用 Dockerfile 构建镜像：

```bash
docker build -t kube-user-manager-webui:latest .
docker run -p 8080:8080 \
  -e ADMIN_PASSWORD=secure123 \
  kube-user-manager-webui:latest
```

## 故障排查

### 无法连接 K8s API

检查 ServiceAccount 权限：

```bash
kubectl auth can-i list clusterroles \
  --as=system:serviceaccount:kube-system:kube-user-manager
```

### 登录失败

检查环境变量是否正确设置：

```bash
kubectl exec -it <pod-name> -n kube-system -- env | grep ADMIN
```

### CORS 错误

检查 `config.py` 中的 `CORS_ORIGINS` 配置。

## 许可证

**Apache-2.0**

