"""
配置文件 (config.py)
=====================
本模块负责加载和管理项目的所有配置参数，包括：
- LLM提供商配置（AWS Bedrock / Azure OpenAI）
- Pinecone向量数据库配置
- PostgreSQL数据库连接
- LangSmith追踪配置
- 业务逻辑阈值参数

所有配置都从环境变量中读取，使用 .env 文件进行本地开发。
"""

from dotenv import load_dotenv; 
import os

# ========== LLM 提供商配置 ==========
# 支持 AWS Bedrock 和 Azure OpenAI 两种 LLM 提供商
LLM_PROVIDER = os.getenv("LLM_PROVIDER","bedrock")  # LLM提供商类型：bedrock 或 azure
AWS_REGION = os.getenv("AWS_REGION","us-west-2")    # AWS Bedrock 服务区域
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT","")      # Azure OpenAI 端点URL
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY","")               # Azure OpenAI API密钥
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT","") # Azure OpenAI 部署名称

# ========== Pinecone 向量数据库配置 ==========
# Pinecone 用于存储和检索医疗知识库（症状、疾病、诊疗路径）
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY","")                    # Pinecone API密钥
PINECONE_ENV = os.getenv("PINECONE_ENV","us-east-1")                   # Pinecone 环境区域
PINECONE_SYMPTOM_INDEX = os.getenv("PINECONE_SYMPTOM_INDEX","symptom-index")        # 症状索引名称
PINECONE_CONDITION_INDEX = os.getenv("PINECONE_CONDITION_INDEX","condition-index")  # 疾病索引名称
PINECONE_CAREPATH_INDEX = os.getenv("PINECONE_CAREPATH_INDEX","carepath-index")     # 诊疗路径索引名称

# ========== 数据库配置 ==========
# PostgreSQL 用于持久化存储分诊请求日志和结果
POSTGRES_URL = os.getenv("POSTGRES_URL","postgresql+psycopg2://user:pass@localhost:5432/triage")

# ========== 可观测性配置 ==========
# LangSmith 用于追踪和调试 LangGraph 的执行过程
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY","")

# ========== 服务配置 ==========
PORT = int(os.getenv("PORT","8080"))  # FastAPI 服务端口

# ========== 业务逻辑阈值参数 ==========
VOTE_PASSES = 3          # 投票轮数：进行多少次推理轮次来聚合结果
AGREEMENT_MIN = 0.55     # 最小一致性阈值：多个推理结果的一致性必须达到此值
CONFIDENCE_MIN = 0.55    # 最小置信度阈值：分诊建议的置信度必须达到此值

# 红色标志词集合：包含这些词的症状会被直接路由到急诊科
RED_FLAG_TERMS = {
    "chest pain",           # 胸痛
    "shortness of breath",  # 呼吸困难
    "one-sided weakness",   # 单侧无力
    "slurred speech"        # 言语不清
}
