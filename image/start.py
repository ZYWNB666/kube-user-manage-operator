"""
统一启动脚本 - 同时运行 Operator 和 Web UI
"""
import asyncio
import multiprocessing
import subprocess
import sys
import os
import uvicorn


def run_operator():
    """运行 Kopf Operator"""
    print("🚀 启动 Kopf Operator...")
    subprocess.run([
        "kopf", "run",
        "--all-namespaces",
        "main.py",
        "--verbose"
    ])


def run_webui():
    """运行 Web UI"""
    print("🌐 启动 Web UI...")
    uvicorn.run(
        "webui_app:app",
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )


if __name__ == "__main__":
    # 使用多进程同时运行两个服务
    operator_process = multiprocessing.Process(target=run_operator)
    webui_process = multiprocessing.Process(target=run_webui)
    
    try:
        print("=" * 50)
        print("Kube User Manager 启动中...")
        print("=" * 50)
        
        operator_process.start()
        webui_process.start()
        
        print("✅ Operator 进程 PID:", operator_process.pid)
        print("✅ Web UI 进程 PID:", webui_process.pid)
        print("🌐 Web 界面: http://0.0.0.0:8080")
        print("=" * 50)
        
        # 等待进程
        operator_process.join()
        webui_process.join()
        
    except KeyboardInterrupt:
        print("\n⚠️ 收到退出信号，正在关闭...")
        operator_process.terminate()
        webui_process.terminate()
        operator_process.join()
        webui_process.join()
        print("✅ 服务已停止")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        operator_process.terminate()
        webui_process.terminate()
        sys.exit(1)

