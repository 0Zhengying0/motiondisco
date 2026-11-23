# 任务 5480104 性能采集核验

数组项 `5480104_5` 于 2026 年 11 月 23 日 00:57–02:39（Europe/Prague）完成 `motiondisco.move_through_clutter` 搜索。Slurm 状态为 `COMPLETED`，退出码 `0:0`。15 个候选均有最终评估，5 个 TO 收敛并通过有效性与保存轨迹的终态检查。KSO、TO 计时、配置追溯和新旧统计兼容性均已验证。GPU 分配与型号可核对，使用率和显存采样缺失。 [作业日志](../logs/md-campaign-5480104_5.out) · [作业事件](../logs/md-campaign-5480104_5.performance.jsonl)

## 新增记录与核验结果

与 `5481702_5` 的阶段对照、CPU 求解路径和 Qwen 推理设备见 [两次作业的 CPU 与 GPU 使用分析](jobs_5480104_5481702_gpu_cpu_analysis.md)。

| 项目 | 结果 |
| --- | --- |
| 阶段实测 | 新增按代记录的单调时钟起止事件。14 次提案累计 **723.11 s**，15 次评估累计 **5,274.38 s**，11 个候选进入 KSO、TO，分别累计 **739.96 s** 和 **4,522.81 s**。TO 求解子阶段累计 **4,473.35 s**。核对了逐阶段起止差与 CSV，未发现未闭合区间。子阶段包含在上层耗时内。 |
| CPU 与主机内存 | Slurm 墙钟 **6,148 s**，分配 **16 CPU**，`TotalCPU` 为 **13,162 CPU 秒**（平均使用 2.14 核），`.batch` 峰值 RSS 为 **21.46 GiB**，请求内存为 **121.25 GiB**。Ollama 日志记录 CPU 型号为 AMD EPYC 7763。 |
| GPU | Slurm 分配 **1 张 GPU**，累计 **1.708 GPU 分配小时**。Ollama 识别为 **NVIDIA A100-SXM4-40GB**，设备总显存约 **39.5 GiB**。 [Ollama 日志](../logs/md-campaign-server-5480104.log) |
| 种子与配置 | 运行种子 `20261123` 用于 Python、NumPy 与 `PYTHONHASHSEED`。15 个派生评估种子均逐代核对，26 次 Ollama 聊天 HTTP 发送均记录模型与种子。Hydra 保存搜索配置，逐代事件保存实际 KSO、TO 参数，包括 KSO 上限 50 个接触模式、TO 每模式 20 个节点及 1 个求解工作线程。 [运行记录](../results/md_qwen_campaign/move_through_clutter/job_5480104_5_ollama/run_performance.jsonl) · [Hydra 配置](../results/md_qwen_campaign/move_through_clutter/job_5480104_5_ollama/.hydra/config.yaml) · [第 4 代评估事件](../results/md_qwen_campaign/move_through_clutter/job_5480104_5_ollama/gen_4/results/evaluation_performance.jsonl) |
| 代码与模型版本 | MotionDisco 基线 `e94c24c90895a61db22db96c4b7e7e3f4ec4b6d8`，工作区有改动，记录的源码差异 SHA-256 与当前工作区吻合。FARO 为 `458afa0cef22b498a68aaccb232e08942880f333`，工作区干净。作业事件保存三个 Ollama 模型的完整摘要。复现本次代码需同时保留 MotionDisco 的工作区源码。 |

## 使用与测试

在 MotionDisco 仓库根目录运行。详细提取器生成 `motiondisco_runs.csv`、`motiondisco_scene_summary.csv` 和 `motiondisco_candidate_performance.csv`。Slurm 账务可访问时用 `--refresh-sacct`，离线时可改用 `--sacct /path/to/karolina_sacct.psv` 读取已包含目标任务的快照。采集参数见[运行文档](../docs/qwen_campaign.md#单场景性能采集验证)。

```bash
python3 scripts/summarize_qwen_campaign.py
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py --refresh-sacct
../envs/motiondisco/bin/python -m unittest discover -s tests -p test_performance_recording.py
```

- 原有简表与详细提取器均用真实新旧产物验证，在临时目录分别生成 21 条简表记录，以及 49 条运行、13 条分组场景和 15 条逐候选记录。对照 `5447792_5` 和 `5456437_5`，历史有效轨迹分别为 2 条，且均与原统计一致。`5456437_5` 的第 9 代仍是 `pending`，简表计入 15 份观察记录，详细表计入 14 份最终评估。
- 6 项性能记录单元测试全部通过，覆盖中断记录、嵌套计时、种子、HTTP 重试和模拟 GPU 采样。两个启动脚本通过 `bash -n`。本次详细提取使用历史账务快照与单任务 `sacct` 查询合成的临时快照，批量刷新遇到账务连接错误。运行环境缺少 `pytest`，因此测试范围为上述用例和实际产物核验。

## 缺失、不可获取与不适用

| 状态 | 本次证据 |
| --- | --- |
| 不可获取 | 原作业的 15 秒采样器记录 `CalledProcessError`，成功样本数 `gpu_sample_count=0`，旧日志仅保留异常类型。Slurm 也未提供 `gres/gpuutil` 和 `gres/gpumem`，因此原作业的 GPU 利用率和显存用量无法补采。CPU 与 GPU 使用量无法按 KSO、TO 阶段归因。 [原作业 GPU 采样日志](../logs/md-campaign-5480104_5.gpu.jsonl) |
| 未记录 | 两个历史对照的 `seed_evidence=unrecorded`，新增的逐候选 KSO、TO 计时列为空。中断后的未闭合阶段可用 `open_timing_spans` 查找，当前任务为 `0`。 |
| 不适用 | 第 0 代为初始程序，提案耗时为空。4 个候选未进入 KSO、TO，其阶段耗时为空。本次未启用分段 TO 和末尾精修，场景未配置物体搬运目标，相关列为空。CSV 使用空值表示多种原因，需结合状态、配置和原始事件区分。 |

## GPU 采样故障复现与修复

旧采样器把 `SLURM_JOB_GPUS` 的节点全局编号传给 `nvidia-smi`。Karolina 的作业设备隔离让 `nvidia-smi` 只看到分配到的 GPU，单卡作业内编号为 `0`。原作业日志只记录编号来源。同节点 `acn10` 的诊断作业 `5481690` 中，Slurm 给出的编号为 `7`，旧采样器发出的命令如下。

```bash
nvidia-smi --query-gpu=uuid,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits --id=7
```

该命令退出码为 `6`，stdout 为 `No devices were found`，stderr 为空。改用作业内编号 `0` 或可见 GPU 的 UUID，退出码为 `0`。前置探针 `5481673` 也在 `acn02` 用全局编号 `4` 复现了相同错误。 [acn10 命令与输出](../logs/md-gpu-diagnostic-5481690.out) · [acn02 命令与输出](../logs/md-gpu-diagnostic-5481673.out)

修复后的采样器在可见 GPU 数量与 Slurm 分配相符时按 UUID 采样，并在失败事件中记录命令、退出码、stdout 和 stderr。同节点诊断仅运行一个短 CUDA 负载，9 秒完成，成功写入两条样本，利用率分别为 **25%**、**92%**，显存占用均为 **553 MiB**。统计读取器成功汇总这两条样本，7 项性能记录单元测试全部通过。 [采样器](../scripts/karolina_performance.py) · [诊断采样记录](../logs/md-gpu-diagnostic-5481690.gpu.jsonl)
