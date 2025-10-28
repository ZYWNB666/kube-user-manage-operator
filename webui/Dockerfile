FROM python:3.11-slim

WORKDIR /app

# 复制后端代码
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# 安装依赖
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动应用
CMD ["python", "/app/backend/app.py"]

