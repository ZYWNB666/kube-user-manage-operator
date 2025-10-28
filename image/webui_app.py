"""
Web UI 应用 - 集成到 Operator 中
"""
from datetime import timedelta
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from webui_auth import Token, User, authenticate_user, create_access_token, get_current_user
from webui_k8s import k8s_client
from webui_config import settings

app = FastAPI(
    title="Kube User Manager",
    description="Kubernetes 用户权限管理系统",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class RoleItem(BaseModel):
    name: str
    namespace: str


class LensUserCreate(BaseModel):
    name: str
    namespace: str = "kube-system"
    roles: List[RoleItem]


class LensUserUpdate(BaseModel):
    roles: List[RoleItem]


class PolicyRule(BaseModel):
    apiGroups: List[str] = []
    resources: List[str] = []
    verbs: List[str] = []
    resourceNames: List[str] = []


class ClusterRoleCreate(BaseModel):
    name: str
    description: str = ""
    rules: List[PolicyRule]


class ClusterRoleUpdate(BaseModel):
    description: str = ""
    rules: List[PolicyRule]


# ==================== 认证接口 ====================

@app.post("/api/login", response_model=Token, tags=["认证"])
async def login(request: LoginRequest):
    """用户登录"""
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me", response_model=User, tags=["认证"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


# ==================== LensUser 管理接口 ====================

@app.get("/api/lensusers", tags=["用户管理"])
async def list_lensusers(
    namespace: str = "kube-system",
    current_user: User = Depends(get_current_user)
):
    """列出所有用户"""
    try:
        users = k8s_client.list_lensusers(namespace)
        return {"success": True, "data": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lensusers/{name}", tags=["用户管理"])
async def get_lensuser(
    name: str,
    namespace: str = "kube-system",
    current_user: User = Depends(get_current_user)
):
    """获取单个用户"""
    try:
        user = k8s_client.get_lensuser(name, namespace)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"success": True, "data": user}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lensusers", tags=["用户管理"])
async def create_lensuser(
    request: LensUserCreate,
    current_user: User = Depends(get_current_user)
):
    """创建用户"""
    try:
        existing = k8s_client.get_lensuser(request.name, request.namespace)
        if existing:
            raise HTTPException(status_code=400, detail="用户已存在")
        
        roles = [{"name": role.name, "namespace": role.namespace} for role in request.roles]
        result = k8s_client.create_lensuser(request.name, roles, request.namespace)
        return {"success": True, "data": result, "message": "用户创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/lensusers/{name}", tags=["用户管理"])
async def update_lensuser(
    name: str,
    request: LensUserUpdate,
    namespace: str = "kube-system",
    current_user: User = Depends(get_current_user)
):
    """更新用户权限"""
    try:
        existing = k8s_client.get_lensuser(name, namespace)
        if not existing:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        roles = [{"name": role.name, "namespace": role.namespace} for role in request.roles]
        result = k8s_client.update_lensuser(name, roles, namespace)
        return {"success": True, "data": result, "message": "用户更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/lensusers/{name}", tags=["用户管理"])
async def delete_lensuser(
    name: str,
    namespace: str = "kube-system",
    current_user: User = Depends(get_current_user)
):
    """删除用户"""
    try:
        result = k8s_client.delete_lensuser(name, namespace)
        return {"success": True, "data": result, "message": "用户删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lensusers/{name}/kubeconfig", tags=["用户管理"])
async def get_user_kubeconfig(
    name: str,
    namespace: str = "kube-system",
    current_user: User = Depends(get_current_user)
):
    """获取用户的 kubeconfig"""
    try:
        # 首先检查用户是否存在
        user = k8s_client.get_lensuser(name, namespace)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        
        # 检查用户状态
        status = user.get("status", {})
        kopf_status = status.get("kopf", {})
        progress = kopf_status.get("progress", {})
        
        # 检查是否有创建失败的记录
        for key, value in progress.items():
            if isinstance(value, dict) and value.get("failure"):
                error_msg = value.get("message", "创建失败")
                raise HTTPException(
                    status_code=500, 
                    detail=f"用户创建失败: {error_msg}。请检查 Operator 权限配置或联系管理员。"
                )
        
        # 获取配置
        luconfig = k8s_client.get_luconfig(name, namespace)
        if not luconfig:
            raise HTTPException(
                status_code=404, 
                detail="Kubeconfig 配置尚未生成，请稍后再试。如果长时间未生成，请检查 Operator 日志。"
            )
        return {"success": True, "data": luconfig.get("spec", {})}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ClusterRole 管理接口 ====================

@app.get("/api/clusterroles", tags=["角色管理"])
async def list_clusterroles(current_user: User = Depends(get_current_user)):
    """列出所有带 UserManager 标签的 ClusterRole"""
    try:
        roles = k8s_client.list_managed_clusterroles()
        return {"success": True, "data": roles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clusterroles/{name}", tags=["角色管理"])
async def get_clusterrole(
    name: str,
    current_user: User = Depends(get_current_user)
):
    """获取单个 ClusterRole"""
    try:
        role = k8s_client.get_clusterrole(name)
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")
        return {"success": True, "data": role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clusterroles", tags=["角色管理"])
async def create_clusterrole(
    request: ClusterRoleCreate,
    current_user: User = Depends(get_current_user)
):
    """创建 ClusterRole"""
    try:
        existing = k8s_client.get_clusterrole(request.name)
        if existing:
            raise HTTPException(status_code=400, detail="角色已存在")
        
        rules = [rule.dict() for rule in request.rules]
        result = k8s_client.create_clusterrole(request.name, rules, request.description)
        return {"success": True, "data": result, "message": "角色创建成功"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "is forbidden" in error_msg and "attempting to grant RBAC permissions" in error_msg:
            raise HTTPException(
                status_code=500, 
                detail="权限不足：Operator 没有足够的权限创建此角色。请重新部署 Helm Chart 以更新权限：helm upgrade kube-user-manager ./helm-chart -n kube-system"
            )
        raise HTTPException(status_code=500, detail=error_msg)


@app.put("/api/clusterroles/{name}", tags=["角色管理"])
async def update_clusterrole(
    name: str,
    request: ClusterRoleUpdate,
    current_user: User = Depends(get_current_user)
):
    """更新 ClusterRole"""
    try:
        existing = k8s_client.get_clusterrole(name)
        if not existing:
            raise HTTPException(status_code=404, detail="角色不存在")
        
        rules = [rule.dict() for rule in request.rules]
        result = k8s_client.update_clusterrole(name, rules, request.description)
        return {"success": True, "data": result, "message": "角色更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "is forbidden" in error_msg and "attempting to grant RBAC permissions" in error_msg:
            raise HTTPException(
                status_code=500, 
                detail="权限不足：Operator 没有足够的权限更新此角色。请重新部署 Helm Chart 以更新权限：helm upgrade kube-user-manager ./helm-chart -n kube-system"
            )
        raise HTTPException(status_code=500, detail=error_msg)


@app.delete("/api/clusterroles/{name}", tags=["角色管理"])
async def delete_clusterrole(
    name: str,
    current_user: User = Depends(get_current_user)
):
    """删除 ClusterRole"""
    try:
        result = k8s_client.delete_clusterrole(name)
        return {"success": True, "data": result, "message": "角色删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 命名空间接口 ====================

@app.get("/api/namespaces", tags=["系统"])
async def list_namespaces(current_user: User = Depends(get_current_user)):
    """列出所有命名空间"""
    try:
        namespaces = k8s_client.list_namespaces()
        return {"success": True, "data": namespaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 静态文件服务 ====================

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    # 先挂载根路径的 index.html
    @app.get("/")
    async def serve_frontend():
        """服务前端页面"""
        return FileResponse(os.path.join(frontend_path, "index.html"))
    
    # 然后挂载静态文件目录
    app.mount("/assets", StaticFiles(directory=frontend_path), name="static")
else:
    @app.get("/")
    async def serve_error():
        return {"error": "Frontend files not found", "path": frontend_path}

