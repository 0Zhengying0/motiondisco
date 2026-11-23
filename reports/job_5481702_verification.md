# 任务 5481702 性能采集核验

`5481702_5` 于 2026 年 11 月 23 日 10:25–12:08（Europe/Prague）在 `acn02` 完成 `motiondisco.move_through_clutter`，Slurm 状态为 `COMPLETED`，退出码 `0:0`。15 个候选均完成评估，其中 5 个 TO 收敛、有效并通过保存轨迹的终态检查。与 `5480104_5` 相比，本次新增了可用的 GPU 利用率和显存序列，采样器按 GPU UUID 成功采集 **415 条样本**。 [作业日志](../logs/md-campaign-5481702_5.out) · [GPU 采样日志](../logs/md-campaign-5481702_5.gpu.jsonl)

## 实测与追溯

GPU 样本与求解阶段及 Ollama 请求的时间对齐见 [两次作业的 CPU 与 GPU 使用分析](jobs_5480104_5481702_gpu_cpu_analysis.md)。

| 项目 | 核验结果 |
| --- | --- |
| 阶段耗时 | 逐个核对事件的单调时钟起止差。14 个提案累计 **683.90 s**，15 个评估累计 **5,318.10 s**，KSO 和 TO 各覆盖 11 个候选，分别累计 **802.38 s** 和 **4,505.64 s**。TO 内部求解累计 **4,457.37 s**，已包含在 TO 总耗时中。`open_timing_spans=0`。 [第 4 代评估事件](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/gen_4/results/evaluation_performance.jsonl) |
| CPU 和主机内存 | Slurm 墙钟 **6,222 s**，分配 **16 个 CPU**，`TotalCPU` 为 **13,181 CPU 秒**（平均使用 2.12 核），`.batch` 峰值 RSS 为 **21.41 GiB**。Ollama 记录的 CPU 型号为 AMD EPYC 7763。 [Ollama 日志](../logs/md-campaign-server-5481702.log) |
| GPU | Slurm 分配 **1 张卡**，累计 **1.728 GPU 分配小时**。`nvidia-smi` 每 15 秒采样同一张 NVIDIA A100-SXM4-40GB，无采样错误。采样利用率均值 **2.89%**、最高 **100%**，显存占用均值 **3,332.57 MiB**、最高 **15,109 MiB**，总显存 **40,960 MiB**。原始样本与 CSV 汇总吻合。 [GPU 采样日志](../logs/md-campaign-5481702_5.gpu.jsonl) |
| 种子和求解配置 | 运行种子 `20261123`，核对了 Python 和 NumPy 的播种记录、`PYTHONHASHSEED`、15 个逐代派生种子和 26 次 Ollama 聊天请求的种子。Hydra 保存完整搜索配置，逐代事件保存实际 KSO、TO 参数，其中 KSO 上限为 50 个接触模式，TO 每模式 20 节点、1 个求解工作线程。 [运行元数据](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/run_performance.jsonl) · [Hydra 配置](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/.hydra/config.yaml) |
| 代码和模型版本 | MotionDisco 基线为 `e94c24c90895a61db22db96c4b7e7e3f4ec4b6d8`，运行时有工作区改动，源码差异的 SHA-256 与当前工作区一致。FARO 为 `458afa0cef22b498a68aaccb232e08942880f333`，运行时工作区干净。三个 Ollama 模型的完整 digest 已保存。复现时需同时保留 MotionDisco 的工作区源码。 [运行元数据](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/run_performance.jsonl) · [作业事件](../logs/md-campaign-5481702_5.performance.jsonl) |

## 使用与测试

从 MotionDisco 根目录运行以下命令。原简表重写 `results/qwen_campaign_summary.csv`。详细提取器输出账务快照、逐运行、逐场景及逐候选 CSV，下面写入临时目录。离线时可用 `--sacct` 指定已包含目标作业的快照。相同场景的新作业会自动采样，可通过 `--array=5` 和 `MOTIONDISCO_SEED` 指定场景及种子。 [运行文档](../docs/qwen_campaign.md)

```bash
python3 scripts/summarize_qwen_campaign.py
audit_dir=$(mktemp -d)
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py --refresh-sacct --output-dir "$audit_dir"
../envs/motiondisco/bin/python -m unittest discover -s tests -p test_performance_recording.py
```

- 两套统计均用实际新旧产物通过核验，核验输出写入临时目录。简表读到 22 条记录，详细表读到 50 条运行、13 条分组场景和 30 条带性能记录的候选。`5447792_5` 和 `5456437_5` 的历史有效轨迹数均为 2，与原报告一致。`5456437_5` 保留第 9 代 `pending`，简表计为已观察，详细表计 14 次最终评估。
- 7 项性能记录单元测试全部通过，两个启动脚本均通过 `bash -n`。详细提取器在可访问 Slurm 的环境下成功刷新账务，并与原始阶段事件、GPU 样本和单任务 `sacct` 查询逐项核对。

## 缺失、不可获取与不适用

| 状态 | 标记及口径 |
| --- | --- |
| 本次不可获取 | Slurm 的 GPU 利用率和显存 TRES 字段为空，`gpu_util_source` 与 `gpu_vram_source` 均标为 `nvidia-smi`。15 秒采样只能给出样本均值和观测峰值，每个进程或每个 KSO／TO 阶段的资源用量、采样间隔内的显存峰值均无法确定。 |
| 历史未记录或采集失败 | 早期作业的 `seed_evidence=unrecorded`，阶段和 GPU 样本数为空。`5480104_5` 的 `gpu_sample_count=0`，原始事件标记 `sampler_error`。`5481702_5` 已有样本中的利用率或显存 `0` 是实测值。 |
| 本次不适用 | 初始程序第 0 代没有提案耗时。第 0、11、12、14 代未进入 KSO 或 TO。分段 TO、末尾精修和物体搬运目标未启用。相关列为空，需结合覆盖数、配置或事件区分原因，CSV 空值本身未细分这些状态。 |
