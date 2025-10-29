#!/bin/bash

##############################################################################
# Kube User Manager 完全清理脚本
# 用途：清理所有相关资源，包括 CRD、用户、Operator 等
##############################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
CRD_GROUP="osip.cc"
NAMESPACE="kube-system"
RELEASE_NAME="kube-user-manager"
FORCE_DELETE=false
SKIP_CONFIRM=false

# 打印函数
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# 帮助信息
show_help() {
    cat << EOF
Kube User Manager 清理脚本

用法: $0 [选项]

选项:
    --crd-group <group>        指定 CRD 组名 (默认: osip.cc)
    --namespace <namespace>    指定命名空间 (默认: kube-system)
    --release-name <name>      指定 Helm Release 名称 (默认: kube-user-manager)
    --force                    强制删除，跳过确认
    --skip-confirm            跳过确认提示
    -h, --help                显示帮助信息

示例:
    # 使用默认配置清理
    $0

    # 自定义 CRD 组名
    $0 --crd-group garena.com

    # 强制删除，不询问
    $0 --force --skip-confirm

EOF
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --crd-group)
            CRD_GROUP="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        --force)
            FORCE_DELETE=true
            shift
            ;;
        --skip-confirm)
            SKIP_CONFIRM=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 确认清理
if [ "$SKIP_CONFIRM" = false ]; then
    print_header "Kube User Manager 清理确认"
    echo "即将清理以下配置："
    echo "  • CRD 组名: $CRD_GROUP"
    echo "  • 命名空间: $NAMESPACE"
    echo "  • Helm Release: $RELEASE_NAME"
    echo ""
    print_warning "此操作将删除所有相关资源，包括："
    echo "  - 所有 LensUser 和 LuConfig 资源"
    echo "  - 相关的 ServiceAccount 和 RoleBinding"
    echo "  - Operator 部署和 Web UI"
    echo "  - CRD 定义"
    echo ""
    read -p "确认继续? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "取消清理"
        exit 0
    fi
fi

print_header "开始清理 Kube User Manager"

# 1. 删除所有 LensUser 资源
print_info "1. 删除所有 LensUser 资源..."
if kubectl get crd "lensuser.${CRD_GROUP}" &> /dev/null; then
    LENSUSER_COUNT=$(kubectl get lensuser -A --no-headers 2>/dev/null | wc -l)
    if [ "$LENSUSER_COUNT" -gt 0 ]; then
        print_info "发现 $LENSUSER_COUNT 个 LensUser 资源"
        if [ "$FORCE_DELETE" = true ]; then
            kubectl delete lensuser --all -A --force --grace-period=0 2>/dev/null || true
        else
            kubectl delete lensuser --all -A 2>/dev/null || true
        fi
        print_success "LensUser 资源已删除"
    else
        print_info "未发现 LensUser 资源"
    fi
else
    print_info "LensUser CRD 不存在，跳过"
fi

# 2. 删除所有 LuConfig 资源
print_info "2. 删除所有 LuConfig 资源..."
if kubectl get crd "luconfig.${CRD_GROUP}" &> /dev/null; then
    LUCONFIG_COUNT=$(kubectl get luconfig -A --no-headers 2>/dev/null | wc -l)
    if [ "$LUCONFIG_COUNT" -gt 0 ]; then
        print_info "发现 $LUCONFIG_COUNT 个 LuConfig 资源"
        if [ "$FORCE_DELETE" = true ]; then
            kubectl delete luconfig --all -A --force --grace-period=0 2>/dev/null || true
        else
            kubectl delete luconfig --all -A 2>/dev/null || true
        fi
        print_success "LuConfig 资源已删除"
    else
        print_info "未发现 LuConfig 资源"
    fi
else
    print_info "LuConfig CRD 不存在，跳过"
fi

# 3. 卸载 Helm Release
print_info "3. 卸载 Helm Release..."
if helm list -n "$NAMESPACE" | grep -q "$RELEASE_NAME"; then
    helm uninstall "$RELEASE_NAME" -n "$NAMESPACE"
    print_success "Helm Release 已卸载"
else
    print_info "未发现 Helm Release: $RELEASE_NAME"
    
    # 如果不是 Helm 部署，尝试手动删除
    print_info "尝试手动删除 Deployment..."
    kubectl delete deployment "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || true
    kubectl delete service "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || true
fi

# 4. 删除 ServiceAccount 和 RBAC
print_info "4. 删除 ServiceAccount 和 RBAC..."
kubectl delete serviceaccount "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || true
kubectl delete clusterrolebinding "$RELEASE_NAME" 2>/dev/null || true
kubectl delete clusterrole "$RELEASE_NAME" 2>/dev/null || true
print_success "ServiceAccount 和 RBAC 已删除"

# 5. 删除管理的 ClusterRole
print_info "5. 删除管理的 ClusterRole..."
MANAGED_ROLES=$(kubectl get clusterrole -l "usermanager.${CRD_GROUP}/managed=true" --no-headers 2>/dev/null | awk '{print $1}')
if [ -n "$MANAGED_ROLES" ]; then
    echo "$MANAGED_ROLES" | while read role; do
        kubectl delete clusterrole "$role" 2>/dev/null || true
        print_info "  删除 ClusterRole: $role"
    done
    print_success "管理的 ClusterRole 已删除"
else
    print_info "未发现管理的 ClusterRole"
fi

# 6. 删除 CRD
print_info "6. 删除 CRD..."
if kubectl get crd "lensuser.${CRD_GROUP}" &> /dev/null; then
    if [ "$FORCE_DELETE" = true ]; then
        kubectl delete crd "lensuser.${CRD_GROUP}" --force --grace-period=0 2>/dev/null || true
    else
        kubectl delete crd "lensuser.${CRD_GROUP}" 2>/dev/null || true
    fi
    print_success "LensUser CRD 已删除"
else
    print_info "LensUser CRD 不存在"
fi

if kubectl get crd "luconfig.${CRD_GROUP}" &> /dev/null; then
    if [ "$FORCE_DELETE" = true ]; then
        kubectl delete crd "luconfig.${CRD_GROUP}" --force --grace-period=0 2>/dev/null || true
    else
        kubectl delete crd "luconfig.${CRD_GROUP}" 2>/dev/null || true
    fi
    print_success "LuConfig CRD 已删除"
else
    print_info "LuConfig CRD 不存在"
fi

# 7. 删除 Ingress (如果存在)
print_info "7. 检查并删除 Ingress..."
if kubectl get ingress "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
    kubectl delete ingress "$RELEASE_NAME" -n "$NAMESPACE" 2>/dev/null || true
    print_success "Ingress 已删除"
else
    print_info "未发现 Ingress"
fi

# 8. 验证清理结果
print_header "验证清理结果"

check_resource() {
    local resource_type=$1
    local label=$2
    local namespace_flag=$3
    
    if [ -n "$label" ]; then
        COUNT=$(kubectl get "$resource_type" -l "$label" $namespace_flag --no-headers 2>/dev/null | wc -l)
    else
        COUNT=$(kubectl get "$resource_type" $namespace_flag --no-headers 2>/dev/null | wc -l)
    fi
    
    if [ "$COUNT" -eq 0 ]; then
        print_success "$resource_type: 清理完成 ✓"
        return 0
    else
        print_warning "$resource_type: 仍有 $COUNT 个资源"
        return 1
    fi
}

ALL_CLEAN=true

# 检查 CRD
if kubectl get crd "lensuser.${CRD_GROUP}" &> /dev/null; then
    print_warning "LensUser CRD 仍然存在"
    ALL_CLEAN=false
else
    print_success "LensUser CRD: 已删除 ✓"
fi

if kubectl get crd "luconfig.${CRD_GROUP}" &> /dev/null; then
    print_warning "LuConfig CRD 仍然存在"
    ALL_CLEAN=false
else
    print_success "LuConfig CRD: 已删除 ✓"
fi

# 检查 Deployment
if kubectl get deployment "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
    print_warning "Deployment 仍然存在"
    ALL_CLEAN=false
else
    print_success "Deployment: 已删除 ✓"
fi

# 检查 Service
if kubectl get service "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
    print_warning "Service 仍然存在"
    ALL_CLEAN=false
else
    print_success "Service: 已删除 ✓"
fi

# 检查 ServiceAccount
if kubectl get serviceaccount "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
    print_warning "ServiceAccount 仍然存在"
    ALL_CLEAN=false
else
    print_success "ServiceAccount: 已删除 ✓"
fi

# 检查 ClusterRole
if kubectl get clusterrole -l "usermanager.${CRD_GROUP}/managed=true" --no-headers 2>/dev/null | grep -q .; then
    print_warning "管理的 ClusterRole 仍然存在"
    ALL_CLEAN=false
else
    print_success "管理的 ClusterRole: 已清理 ✓"
fi

echo ""
if [ "$ALL_CLEAN" = true ]; then
    print_header "清理完成！"
    print_success "所有资源已成功清理"
else
    print_header "清理完成（部分资源可能需要手动清理）"
    print_warning "部分资源仍然存在，请查看上方警告信息"
    echo ""
    print_info "如需强制清理，运行: $0 --force"
fi

echo ""
print_info "详细清理指南请参考: UNINSTALL.md"

