# 紧急修复脚本 - 清理 Terminating CRD
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "清理 Terminating 状态的 CRD" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 删除所有 LensUser 资源
Write-Host "`n[1/6] 删除所有 LensUser 资源..." -ForegroundColor Yellow
kubectl delete lensuser --all -A --ignore-not-found=true

# 2. 删除所有 LuConfig 资源
Write-Host "[2/6] 删除所有 LuConfig 资源..." -ForegroundColor Yellow
kubectl delete luconfig --all -A --ignore-not-found=true

# 3. 等待资源删除
Write-Host "[3/6] 等待资源删除..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 4. 强制删除 CRD（移除 finalizer）
Write-Host "[4/6] 强制删除 lensuser CRD..." -ForegroundColor Yellow
kubectl patch crd lensuser.osip.cc -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge 2>$null
kubectl delete crd lensuser.osip.cc --ignore-not-found=true 2>$null

Write-Host "[5/6] 强制删除 luconfig CRD..." -ForegroundColor Yellow
kubectl patch crd luconfig.osip.cc -p '{\"metadata\":{\"finalizers\":[]}}' --type=merge 2>$null
kubectl delete crd luconfig.osip.cc --ignore-not-found=true 2>$null

# 5. 等待 CRD 完全删除
Write-Host "[6/6] 等待 CRD 完全删除..." -ForegroundColor Yellow
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    $crds = kubectl get crd 2>$null | Select-String "osip.cc"
    if (-not $crds) {
        Write-Host "✅ CRD 已完全删除" -ForegroundColor Green
        break
    }
    Write-Host "   等待中... ($waited/$maxWait 秒)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $waited += 2
}

# 6. 重新安装 Helm Chart
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "重新安装 Helm Chart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查是否已安装
$existing = helm list -n kube-system 2>$null | Select-String "kube-user-manager"
if ($existing) {
    Write-Host "升级现有安装..." -ForegroundColor Yellow
    helm upgrade kube-user-manager ./helm-chart -n kube-system
} else {
    Write-Host "全新安装..." -ForegroundColor Yellow
    helm install kube-user-manager ./helm-chart -n kube-system
}

# 7. 等待 Pod 就绪
Write-Host "`n等待 Pod 启动..." -ForegroundColor Yellow
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kube-user-manager -n kube-system --timeout=60s 2>$null

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✅ 修复完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`n请验证:" -ForegroundColor Cyan
Write-Host "1. kubectl get crd | Select-String osip.cc" -ForegroundColor White
Write-Host "2. kubectl get pods -n kube-system | Select-String kube-user-manager" -ForegroundColor White

