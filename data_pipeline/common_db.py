"""
PostgreSQL 数据库连接工具

该模块提供统一的数据库连接管理功能，使用上下文管理器确保连接的正确关闭和事务提交。

主要功能：
1. 从环境变量或 .env 文件加载数据库连接配置
2. 提供 pg_conn() 上下文管理器，自动处理连接的创建、提交和关闭
3. 确保即使发生异常也能正确关闭连接
"""

# data_pipeline/common_db.py
import os
import psycopg2
from contextlib import contextmanager
from dotenv import load_dotenv

# 加载环境变量（从 data_pipeline/.env 文件）
# os.path.dirname(__file__): 获取当前文件所在目录
# 这样可以确保从 data_pipeline 文件夹下的 .env 文件加载配置

# PostgreSQL 连接配置字典
# 从环境变量读取配置，如果不存在则使用默认值
PG_CONN_INFO = {
    "host": os.getenv("PG_HOST", "127.0.0.1"),      # 数据库主机地址，默认本地
    "port": int(os.getenv("PG_PORT", "5432")),      # 数据库端口，默认 5432
    "dbname": os.getenv("PG_DB", "triage"),         # 数据库名称，默认 triage
    "user": os.getenv("PG_USER", "qiaohui"),        # 数据库用户名，默认 qiaohui
    "password": os.getenv("PG_PASSWORD", ""),       # 数据库密码，默认空字符串
}

@contextmanager
def pg_conn():
    """
    安全获取 PostgreSQL 连接的上下文管理器
    
    使用方式：
        with pg_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
            # 自动提交和关闭连接
    
    功能：
        - 自动创建数据库连接
        - 执行完代码块后自动提交事务（conn.commit()）
        - 无论是否发生异常，都会自动关闭连接（conn.close()）
        - 使用上下文管理器确保资源正确释放
    """
    # 创建数据库连接
    conn = psycopg2.connect(**PG_CONN_INFO)
    try:
        # yield 将连接对象传递给 with 语句块
        yield conn
        # 代码块执行成功后，提交事务
        conn.commit()
    finally:
        # 无论是否发生异常，都关闭连接
        conn.close()