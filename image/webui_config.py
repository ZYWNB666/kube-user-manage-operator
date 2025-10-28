import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # JWT 配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时
    
    # 管理员账号配置（从环境变量读取）
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # K8s 配置
    CLUSTER_NAME: str = os.getenv("cluster_name", "kubernetes")
    KUBE_API_URL: str = os.getenv("kube_api_url", "https://kubernetes.default.svc")
    
    # UserManager 标签
    USER_MANAGER_LABEL: str = "usermanager.osip.cc/managed"
    USER_MANAGER_LABEL_VALUE: str = "true"
    
    # CORS 配置
    CORS_ORIGINS: List[str] = ["*"]
    
    class Config:
        case_sensitive = True


settings = Settings()

