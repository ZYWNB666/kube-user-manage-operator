FROM python:3.11-slim

WORKDIR /app

# 复制所有文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 Web UI 端口
EXPOSE 8080

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动统一服务
CMD ["python", "start.py"]
