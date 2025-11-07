# ========== Docker 镜像构建文件 ==========
# 本文件定义了 AI 分诊代理服务的 Docker 镜像构建过程
# 使用多阶段构建优化镜像大小和构建速度

# ========== 基础镜像 ==========
# 使用 Python 3.11 精简版作为基础镜像
# slim 版本减少了镜像大小，适合生产环境
FROM python:3.11-slim

# ========== 工作目录 ==========
# 设置容器内的工作目录为 /srv
# 所有后续命令都在此目录下执行
WORKDIR /srv

# ========== 依赖安装 ==========
# 复制 requirements.txt 到容器中
# 安装 Python 依赖包（不包括缓存文件，减小镜像大小）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ========== 应用代码 ==========
# 复制应用代码到容器中
# 复制 app 目录（包含所有 Python 代码）
COPY app app

# ========== 配置文件 ==========
# 复制环境变量示例文件（可选）
# 注意：生产环境应使用实际的 .env 文件或环境变量
COPY .env.example .env.example

# ========== 端口暴露 ==========
# 暴露容器端口 8080
# FastAPI 服务将在该端口上运行
EXPOSE 8080

# ========== 启动命令 ==========
# 容器启动时执行的命令
# 使用 uvicorn 启动 FastAPI 应用
# --host 0.0.0.0: 监听所有网络接口
# --port 8080: 监听端口 8080
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8080"]
