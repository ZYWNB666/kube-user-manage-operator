# 简介
在日常维护中，经常需要给开发开通相关账号权限功能，使用原始命令管理时，无法集中管理和修改用户权限，因为每个`RoleBinding`分散在各自的命名空间。

# 模版
```yaml
apiVersion: garena.com/v1
kind: LensUser
metadata:
  name: dev
  namespace: kube-system
spec:
  roles:
    - name: admin
      namespace: cava
```
> 放在`kube-system`是为了对开发进行隐藏

