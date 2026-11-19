# 本地 Qwen 多场景实验

场景和节点预算见 [`qwen_campaign.tsv`](../scripts/qwen_campaign.tsv)，采用仓库 `run_search.sh` 的 9 个内置基准场景。一次提交全部场景，依次运行。

## 固定设置

- MotionDisco：`0df8eab8623f58b447cd8402836ceffcdd472360`；FARO：`458afa0cef22b498a68aaccb232e08942880f333`。
- 本地模型：Ollama 0.40.16；Qwen Coder 14B（`9ec8897f747e`）生成计划，7B（`dae161e27b0e`）用于辅助调用，embeddinggemma（`85462619ee72`）用于向量检索。
- 搜索：`legacy` 评分、`island_small` 数据库、`small_budget` 演化配置、每次一个评估任务、每次一个提案任务；节点预算按场景表。
- 资源：每个场景使用 1 张 A100、8 个 CPU、最长 12 小时；模型服务与搜索运行在同一个 Slurm 作业中。

## 运行与汇总

在仓库根目录运行：

```bash
# 提交全部 9 个场景；%1 表示同一时间只运行 1 个
sbatch scripts/14_qwen_campaign.sbatch

# 随时汇总已完成的运行
python3 scripts/summarize_qwen_campaign.py
```

同一批作业可再次提交以获得独立重复运行。搜索结果写入 `results/md_qwen_campaign/<scene>/`，汇总表写入 `results/qwen_campaign_summary.csv`。
