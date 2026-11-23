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

同一批可再次提交以获得新的运行记录。逐次配置的种子和采样方式决定能否作为独立重复。搜索结果写入 `results/md_qwen_campaign/<scene>/`，汇总表写入 `results/qwen_campaign_summary.csv`。

## 单场景性能采集验证

在 Karolina 上进入 MotionDisCo 仓库，只提交数组下标 5，运行一次 `motiondisco.move_through_clutter`。

```bash
cd /mnt/proj1/eu-26-37/it4i-dianyu/Zhengying/motiondisco
sbatch --array=5 --export=ALL,MOTIONDISCO_SEED=20261123 scripts/14_qwen_campaign.sbatch
```

该命令沿用第二轮的 15 个搜索节点、`legacy` 评分、`island_small`、`small_budget`、每次一个提案和一个评估、6 次新颖性尝试、单模型驻留、KSO 上限 50 个接触模式和 TO 单工作线程。Apptainer 镜像、Conda 环境、三份本地模型、A100 资源请求和 `BEGIN,END,FAIL` 邮件配置保持原有设置。新增的实验差异是显式播种与性能采集。省略 `MOTIONDISCO_SEED` 时，作业从系统熵生成 31 位种子并记录来源。

作业结束且 Slurm 账务更新后，从仓库根目录刷新统计。

```bash
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py --refresh-sacct
```

### 字段口径与产物

- `run_performance.jsonl` 记录运行配置、种子及 Git 版本，并在 Git 可用时记录工作区源码差异摘要，原有 `.hydra/config.yaml` 和 overrides 保存完整搜索配置。作业级 JSONL 记录启动、退出码和 Ollama 模型完整 digest。Slurm 的 `State`、`ElapsedRaw`、`AllocCPUS`、`TotalCPU` 和步骤 `MaxRSS` 提供作业终态、分配时间、实际 CPU 时间与主机内存。
- 每个候选同时保留原有 `metrics.json`、`extra.json` 和失败分类。提案与评估的 JSONL 按代编号写入，相应时间进入 `motiondisco_candidate_performance.csv`。两个历史 CSV 的字段保留，新增字段在历史行为空。阶段只在实际进入时写入边界，未结束的阶段保留开始事件和已完成子阶段，汇总表用覆盖数和 `open_timing_spans` 表示这些记录。
- `proposal_s` 是提案路径墙钟，`program_generation_s` 累计生成和修补，包括已有重试路径。`candidate_llm_requests` 统计提案内本地聊天的 HTTP 发送尝试，包括新颖性判断和传输重试，embedding 保留原有作业口径。第 0 代初始程序来自仓库。
- `candidate_evaluation_s` 包含候选程序执行、评估及指标写盘，Shinka 数据库仍保留外层流水线时间。`kso_s` 汇总完整 KSO 入口与分段 TO 中的 KSO 窗口。`to_s` 包含分段、最终优化、内嵌 KSO 与物理检查。`to_exclusive_s` 从 TO 墙钟减去内嵌 KSO 和物理检查区间的并集。标记为 `work_s` 的字段累加各调用耗时，分段并行时可以重叠。`to_segmented_s` 与 `to_polish_s` 也包含于 `to_s`。FARO 原生 KSO 计时单独记录在 `kso_native_profiled_s` 和 `kso_native_initialization_s`。
- `gpu_sampled_*` 默认每 15 秒采样作业分配的 GPU，显存单位为 MiB，利用率单位为百分比。CSV 保留 Slurm 的 GPU TRES 并优先标记其来源，单列实测采样均值与观测峰值。GPU 分配小时取作业墙钟乘以分配卡数。GPU 的采样峰值受采样频率影响。主机峰值 RSS 仍取 Slurm。
- 物体数量来自解析后的 FARO 场景，包含地面，并另列固定与可移动物体数。计划搬运距离为每个具有连续位置目标的可移动物体从初始位置到目标位置的直线距离。已返回轨迹另按物体记录首末位移与沿轨迹的累计路径长度，保留对应的候选有效性。无物体位置目标的场景，计划搬运距离留空。
- 搜索进程给 Python 和 NumPy 实际播种，候选进程使用由运行种子与代数派生的种子。Karolina 启动器也在 Python 启动前设置哈希种子。Ollama 聊天请求携带实际使用的 `seed`，逐请求记录模型和种子；SDK 对同一请求的内部重试使用同一负载。异步运行顺序、底层求解及 GPU 执行仍可能影响逐位复现。 [Ollama 聊天 API 字段](https://docs.ollama.com/api/openai-compatibility#supported-request-fields)
- 其他场景搜索可在启动 Hydra 前设置 `MOTIONDISCO_PERFORMANCE=1` 及 `MOTIONDISCO_SEED`，使用 Ollama 时可同时设 `MOTIONDISCO_OLLAMA_SEED=1`。数据生成 worker 在此模式下为每个样本保存阶段 JSONL，并记录已有的变体采样种子、轨迹距离和终态。数据集样本事件位于各自的 plan 输出目录。
