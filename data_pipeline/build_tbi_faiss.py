"""
构建 FAISS 向量索引文件

该脚本从 PostgreSQL 数据库中读取医疗指南的嵌入向量，构建 FAISS 索引用于快速相似度搜索。
FAISS (Facebook AI Similarity Search) 是一个高效的向量相似度搜索库。

主要功能：
1. 从数据库 medical_guidelines 表中读取所有记录的 id 和 embedding
2. 将二进制 embedding 数据转换为 numpy 数组
3. 对向量进行 L2 归一化（使向量长度为1，便于使用内积计算相似度）
4. 使用 IndexFlatIP（内积索引，适合归一化后的向量）构建索引
5. 保存索引文件和对应的 id 映射文件
"""

import numpy as np, faiss, psycopg2
from data_pipeline.common_db import pg_conn

def build_faiss():
    """
    构建 FAISS 向量索引
    
    流程：
    1. 从 PostgreSQL 数据库读取所有医疗指南的嵌入向量
    2. 将二进制数据转换为 numpy 数组
    3. 归一化向量（L2 归一化）
    4. 创建 FAISS 索引并添加向量
    5. 保存索引文件和 id 映射文件
    """
    # 从数据库获取所有医疗指南的 id 和 embedding（二进制格式）
    with pg_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, embedding FROM medical_guidelines")
        rows = cur.fetchall()

    # 将二进制 embedding 数据转换为 numpy 数组
    # np.frombuffer: 从二进制缓冲区创建数组，dtype=np.float32 表示32位浮点数
    vecs = [np.frombuffer(r[1], dtype=np.float32) for r in rows]
    
    # 提取所有记录的 id，转换为 numpy 数组
    ids = np.array([r[0] for r in rows])
    
    # 获取向量的维度（每个向量的长度）
    dim = vecs[0].shape[0]
    
    # 将所有向量堆叠成一个矩阵 (n_vectors, dim)
    # np.vstack: 垂直堆叠，将多个一维数组堆叠成二维矩阵
    mat = np.vstack(vecs)
    
    # L2 归一化：将每个向量除以其 L2 范数，使向量长度为1
    # 归一化后的向量可以使用内积（点积）来计算余弦相似度
    faiss.normalize_L2(mat)
    
    # 创建 FAISS 索引
    # IndexFlatIP: 使用内积（Inner Product）的平面索引
    # 适合归一化后的向量，内积值等于余弦相似度
    index = faiss.IndexFlatIP(dim)
    
    # 将归一化后的向量矩阵添加到索引中
    index.add(mat)
    
    # 保存索引文件到磁盘
    faiss.write_index(index, "index/faiss_tbi.index")
    
    # 保存 id 映射文件（用于根据索引位置查找原始数据库 id）
    np.save("index/faiss_tbi_ids.npy", ids)
    
    print(f"FAISS built with {len(ids)} vectors of dim {dim}")

if __name__ == "__main__":
    build_faiss()