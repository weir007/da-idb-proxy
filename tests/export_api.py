import requests
import json
import os

# 配置信息
API_URL = "http://127.0.0.1:8090/api/v1/export-spec"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SAVE_DIR = os.path.join(PROJECT_ROOT, "doc")
FILE_NAME = "idb-proxy-api.json"
TARGET_PATH = os.path.join(SAVE_DIR, FILE_NAME)


def export_openapi_spec():
    print(f"🚀 开始从 {API_URL} 获取 API 规范...")

    try:
        # 1. 发送请求获取 OpenAPI JSON
        response = requests.get(API_URL, proxies={"http": None, "https": None})
        response.raise_for_status()  # 如果状态码不是 200，抛出异常

        spec_data = response.json()

        # 2. 检查并创建 doc 目录
        if not os.path.exists(SAVE_DIR):
            os.makedirs(SAVE_DIR)
            print(f"📁 已创建目录: {SAVE_DIR}")

        # 3. 写入文件（格式化为易读的 JSON）
        with open(TARGET_PATH, "w", encoding="utf-8") as f:
            json.dump(spec_data, f, indent=4, ensure_ascii=False)

        print(f"✅ 导出成功！文件路径: {TARGET_PATH}")

    except requests.exceptions.ConnectionError:
        print("❌ 错误: 无法连接到服务，请确保 FastAPI 代理服务已启动 (默认 8000 端口)。")
    except Exception as e:
        print(f"❌ 发生意外错误: {e}")


if __name__ == "__main__":
    export_openapi_spec()
