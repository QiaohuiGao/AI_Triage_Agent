# # data_pipeline/embedder.py
# import os
# import numpy as np

# BACKEND = os.getenv("EMBEDDING_BACKEND", "huggingface").lower()

# if BACKEND == "openai":
#     from openai import OpenAI
#     OPENAI_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
#     _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

#     def embed(texts):
#         """
#         输入: List[str]
#         输出: np.array[n, d] (float32)
#         """
#         resp = _client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
#         vecs = [r.embedding for r in resp.data]
#         return np.array(vecs, dtype="float32")

# else:
#     # 默认使用 HuggingFace sentence-transformers
#     from sentence_transformers import SentenceTransformer
#     HF_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
#     _model = SentenceTransformer(HF_MODEL)

#     def embed(texts):
#         """
#         输入: List[str]
#         输出: np.array[n, d] (float32)
#         """
#         vecs = _model.encode(
#             texts,
#             batch_size=16,
#             show_progress_bar=False,
#             normalize_embeddings=True
#         )
#         return np.array(vecs, dtype="float32")

"""
文本嵌入向量生成工具

该模块使用 OpenAI 的嵌入模型将文本转换为高维向量表示。
嵌入向量可以用于语义相似度搜索、文本检索等任务。

主要功能：
1. 使用 OpenAI API 生成文本嵌入向量
2. 支持批量处理多个文本
3. 返回标准化的 numpy 数组格式
"""

import os
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv


# 初始化 OpenAI 客户端
# 从环境变量读取 API 密钥
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ Missing OPENAI_API_KEY in environment variables or .env file")
client = OpenAI(api_key=api_key)

# 默认使用的嵌入模型
# text-embedding-3-small: 较小的模型，速度快，成本低
# 也可以使用 text-embedding-3-large: 更大的模型，精度更高但成本更高
OPENAI_EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

def embed(texts):
    """
    使用 OpenAI 模型生成文本嵌入向量
    
    参数:
        texts: 字符串列表，每个字符串是要嵌入的文本
               - 可以是单个字符串（会自动转换为列表）
               - 也可以是字符串列表（批量处理）
    
    返回:
        np.ndarray: 形状为 (n, d) 的 numpy 数组
                   - n: 输入文本的数量
                   - d: 向量的维度（取决于使用的模型）
                   - 数据类型: float32
    
    注意:
        - OpenAI API 限制单次最多 2048 个输入
        - 每个文本不超过 8192 tokens
        - 返回的向量已经过归一化处理
    """
    # 如果输入是单个字符串，转换为列表以便统一处理
    if isinstance(texts, str):
        texts = [texts]

    print(f"🔹 Generating embeddings via OpenAI model: {OPENAI_EMBED_MODEL}")
    
    # 调用 OpenAI API 生成嵌入向量
    # model: 使用的嵌入模型
    # input: 要嵌入的文本列表
    resp = client.embeddings.create(model=OPENAI_EMBED_MODEL, input=texts)
    
    # 从响应中提取嵌入向量
    # resp.data 是一个列表，每个元素包含一个文本的嵌入向量
    vecs = [r.embedding for r in resp.data]
    
    # 转换为 numpy 数组，数据类型为 float32（32位浮点数）
    return np.array(vecs, dtype="float32")