# AIMETA P=评估基线子系统|R=夹具_配置矩阵_评分器_跑批_报告|NR=不进生产请求链路|E=fixtures_configs_scoring_runner_report|X=internal|A=bench工具包|D=services|S=none
"""评估基线（评估驱动开发）子系统。

在固定基准场景上以不同管线配置生成章节、打分、对比，回答
「每个质量开关的真实贡献是多少」。仅供 run_bench.py CLI 与测试使用，
不接入任何生产请求链路。
"""
