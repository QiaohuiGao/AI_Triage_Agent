"""
Prometheus 监控指标模块 (prometheus_metrics.py)
==============================================
本模块定义 Prometheus 监控指标，用于监控分诊服务的性能和健康状态。

功能：
- 定义分诊请求延迟指标（Histogram）
- 定义成功请求计数指标（Counter）
- 定义错误请求计数指标（Counter）

指标说明：
- triage_request_latency_seconds: 分诊请求的端到端延迟（秒）
- triage_success_total: 成功处理的分诊请求总数
- triage_errors_total: 处理过程中发生的错误总数

用途：
- 性能监控：监控分诊请求的延迟和吞吐量
- 健康检查：监控服务的错误率和成功率
- 告警：当错误率或延迟超过阈值时触发告警
- 可视化：在 Grafana 中可视化监控指标

Prometheus 指标类型：
- Histogram: 用于记录延迟等连续值，支持分位数统计
- Counter: 用于记录计数，只能递增，不能递减
"""

from prometheus_client import Counter, Histogram

# ========== 延迟指标 ==========
# Histogram 类型，用于记录分诊请求的端到端延迟（秒）
# 支持分位数统计（p50, p95, p99）和平均值计算
triage_latency = Histogram(
    "triage_request_latency_seconds",  # 指标名称
    "End-to-end triage request latency"  # 指标描述
)

# ========== 成功指标 ==========
# Counter 类型，用于记录成功处理的分诊请求总数
# 只能递增，不能递减，用于统计成功请求的数量
triage_success = Counter(
    "triage_success_total",  # 指标名称
    "Successful triage requests"  # 指标描述
)

# ========== 错误指标 ==========
# Counter 类型，用于记录处理过程中发生的错误总数
# 只能递增，不能递减，用于统计错误请求的数量
triage_errors = Counter(
    "triage_errors_total",  # 指标名称
    "Errors during triage processing"  # 指标描述
)
