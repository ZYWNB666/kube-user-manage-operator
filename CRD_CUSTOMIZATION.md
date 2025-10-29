# CRD 组名自定义说明

## 概述

从此版本开始，Kube User Manager 支持自定义 CRD 的组名（Group）和版本（Version），您可以根据需要修改为自己的域名。

## 默认配置

- **CRD Group**: `osip.cc`
- **CRD Version**: `v1`

## 自定义方式

### 方法 1：通过环境变量配置

在部署时设置环境变量：

```bash
export CRD_GROUP="your-domain.com"
export CRD_VERSION="v1"
```

### 方法 2：通过 Helm Values 配置

修改 `values.yaml` 文件：

```yaml
operator:
  crd:
    group: "your-domain.com"
    version: "v1"
```

然后使用 Helm 安装或升级：

```bash
helm install kube-user-manager ./helm-chart \
  --set operator.crd.group="your-domain.com" \
  --set operator.crd.version="v1"
```

### 方法 3：直接在 Kubernetes Deployment 中配置

如果您直接使用 Kubernetes YAML 部署，在 Deployment 中添加环境变量：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kube-user-manager
spec:
  template:
    spec:
      containers:
      - name: kube-user-manager
        image: kaifa6599/kube-user-manage-operator:v1.0
        env:
        - name: CRD_GROUP
          value: "your-domain.com"
        - name: CRD_VERSION
          value: "v1"
```

## CRD 资源名称

使用自定义组名后，CRD 的完整名称会自动更新：

- **LensUser CRD**: `lensuser.{your-crd-group}`
- **LuConfig CRD**: `luconfig.{your-crd-group}`

### 示例

如果设置 `CRD_GROUP="example.com"`，CRD 名称将变为：
- `lensuser.example.com`
- `luconfig.example.com`

## 资源定义示例

使用自定义组名后的资源定义：

```yaml
apiVersion: example.com/v1
kind: LensUser
metadata:
  name: test-user
  namespace: kube-system
spec:
  roles:
    - name: admin
      namespace: default
```

## 注意事项

1. **更改组名需要重新部署**：修改 CRD 组名后需要重新部署整个应用
2. **已有资源需要迁移**：如果您已经创建了使用旧组名的资源，需要手动迁移到新组名
3. **保持一致性**：确保所有组件（Operator、Web UI）使用相同的 CRD 组名配置
4. **域名格式**：建议使用有效的域名格式，如 `company.com`、`example.io` 等

## 验证配置

部署后，可以通过以下命令验证 CRD 是否正确创建：

```bash
# 查看 CRD
kubectl get crd | grep lensuser
kubectl get crd | grep luconfig

# 查看 Pod 日志确认配置
kubectl logs -n kube-system deployment/kube-user-manager | grep "Using CRD Group"
```

您应该看到类似以下输出：

```
Using CRD Group: your-domain.com, Version: v1
```

## 迁移现有资源

如果您需要从旧的组名迁移到新的组名：

1. **导出现有资源**：
```bash
kubectl get lensuser.osip.cc -n kube-system -o yaml > old-resources.yaml
```

2. **修改 apiVersion**：
将 `apiVersion: osip.cc/v1` 改为 `apiVersion: your-domain.com/v1`

3. **删除旧资源**：
```bash
kubectl delete lensuser.osip.cc -n kube-system --all
```

4. **应用新资源**：
```bash
kubectl apply -f new-resources.yaml
```

## 技术细节

自定义功能涉及以下文件的修改：

- `image/webui_config.py` - 配置管理
- `image/main.py` - Operator 核心逻辑
- `image/webui_k8s.py` - Web UI 后端
- `image/template/crd.yaml` - LensUser CRD 模板
- `image/template/lu-config-crd.yaml` - LuConfig CRD 模板
- `helm-chart/values.yaml` - Helm 配置
- `helm-chart/templates/operator-deployment.yaml` - Deployment 模板

## 支持

如有问题，请提交 Issue 或查看项目文档。

