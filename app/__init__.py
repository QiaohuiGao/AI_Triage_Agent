import os
from dotenv import load_dotenv

# 在项目根路径中强制加载 .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

key = os.getenv("OPENAI_API_KEY")
if key:
    print(f"✅ OPENAI_API_KEY loaded globally: {key[:10]}...")
else:
    print("❌ OPENAI_API_KEY not found in environment.")
