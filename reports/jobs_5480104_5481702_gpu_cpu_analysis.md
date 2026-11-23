# 任务 5480104 与 5481702 的 CPU 与 GPU 使用分析

`5481702_5` 的 A100 采样利用率均值为 **2.89%**。主要原因是候选评估里的 **KSO 和 TO 走 CPU 求解路径**，两阶段合计覆盖 **85.31%** 的作业墙钟，落在这两个阶段的 **353 个 GPU 样本全部为 0%**。本地 **Qwen2.5-Coder 14B 和 7B 均在 A100 上做模型推理**。全部 35 个非零 GPU 样本都落在 Ollama 的模型请求窗口内，最高观测到 100%。 [GPU 采样](../logs/md-campaign-5481702_5.gpu.jsonl) · [Ollama 日志](../logs/md-campaign-server-5481702.log)

## 两次作业

两次运行均为 `motiondisco.move_through_clutter`，日期为 2026 年 11 月 23 日，时间采用 Europe/Prague（CET）。两次均分配 16 个 CPU 和 1 张 NVIDIA A100-SXM4-40GB，状态为 `COMPLETED`，退出码 `0:0`。运行种子均为 `20261123`，均完成 15 个候选评估，其中 11 个进入 KSO 和 TO，5 条轨迹收敛、有效且达到场景终态目标（第 4、5、8、9、13 代）。 [5480104 核验](job_5480104_verification.md) · [5481702 核验](job_5481702_verification.md)

| 指标 | `5480104_5` | `5481702_5` |
| --- | ---: | ---: |
| 节点及 Slurm 起止时间 | acn10，00:57:16–02:39:44 | acn02，10:25:13–12:08:55 |
| Slurm 墙钟 | 6,148 s | 6,222 s |
| Slurm `TotalCPU` / 墙钟平均使用核心数 | 13,162 CPU 秒 / 2.14 核 | 13,181 CPU 秒 / 2.12 核 |
| 候选评估墙钟合计 | 5,274.38 s（85.79%） | 5,318.10 s（85.47%） |
| KSO 阶段 | 739.96 s（12.04%） | 802.38 s（12.90%） |
| TO 阶段 | 4,522.81 s（73.57%） | 4,505.64 s（72.42%） |
| KSO 与 TO 时间区间并集 | 5,262.77 s（85.60%） | 5,308.02 s（85.31%） |
| TO 的 `to_solve` 子阶段 | 4,473.35 s | 4,457.37 s |
| Ollama 聊天请求数 / 服务耗时合计 | 26 / 607.45 s | 26 / 589.75 s |
| Ollama embedding 请求数 / 服务耗时合计 | 17 / 69.02 s | 17 / 76.52 s |
| GPU 有效样本数 | 0 | 415 |
| GPU 采样均值 / 观测峰值 | — | 2.89% / 100% |
| 显存采样均值 / 观测峰值 | — | 3,332.57 MiB / 15,109 MiB |

阶段耗时来自 `gen_*` 下的逐代 JSONL，按 span 配对，时长与单调时钟差核对。表中百分比以 Slurm 墙钟为分母，`to_solve` 包含在 TO 内，KSO 和 TO 包含在候选评估内。Ollama 耗时来自服务器的 GIN HTTP 日志。 [5480104 阶段和结果](../results/md_qwen_campaign/move_through_clutter/job_5480104_5_ollama) · [5481702 阶段和结果](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama) · [5480104 Ollama 日志](../logs/md-campaign-server-5480104.log)

## 5481702 的 GPU 采样与作业阶段

将 `nvidia-smi` 样本的 `unix_s` 与阶段起止事件对齐。Ollama 请求窗口由 GIN 的结束时间减去该请求的服务耗时得到。

| 采样时段 | 样本数 | 利用率为 0% 的样本 | 平均利用率 | 观测峰值 |
| --- | ---: | ---: | ---: | ---: |
| 全作业 | 415 | 380（91.57%） | 2.89% | 100% |
| 候选评估 | 354 | 354 | 0% | 0% |
| 其中 KSO | 52 | 52 | 0% | 0% |
| 其中 TO | 301 | 301 | 0% | 0% |
| 候选评估之外 | 61 | 26 | 19.64% | 100% |
| 其中 Ollama 聊天和 embedding 请求窗口 | 43 | 8 | 27.86% | 100% |

第 7 代是最长的单次 TO，11:28:10.754–11:44:25.409 持续约 **16 分 15 秒**。前接约 2 分钟 KSO，GPU 从 11:26:01.730 到 11:44:16.731 连续 **74 个样本为 0%**。全作业有 **202 个**样本同时显示非零显存占用和 0% 利用率，候选评估阶段占其中 **182 个**。因此作业在 CPU 上求解时仍可看到卡上有显存占用。 [第 7 代时间线](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/gen_7/results/evaluation_performance.jsonl) · [GPU 采样](../logs/md-campaign-5481702_5.gpu.jsonl)

## CPU 执行路径

- **候选程序、接触计划校验、搜索调度。** Shinka 在本地 Python 评估进程中执行候选程序。两次保存的候选通过 `env` 生成接触列表，随后由 Python 评估器做格式与接触合法性检查、去重和离散目标检查。搜索端的调度、SQLite 读写与向量相似度计算也在主机侧执行。 [候选执行](../shinka/core/wrap_eval.py) · [接触计划评估](../examples/loco_manipulation/evaluate.py) · [搜索数据库](../shinka/database/dbase.py)
- **KSO（运动学可行性检查）。** `ik_eval.py` 构建 FARO `KsoTask`，用 acados 的 `PARTIAL_CONDENSING_HPIPM` 求解，初始化、热启动、碰撞更新和求解都走 CPU 路径。 [KSO 调用](../examples/loco_manipulation/ik_eval.py) · [acados 求解器配置](../submodules/faro/src/faro/solvers/acados_wrapper.py)
- **TO（轨迹优化）。** FARO 通过 Moto 的原生 C++ SQP 求解，数值后端使用 Eigen 和 BLASFEO，两次作业均将 Moto 的 `n_job` 设为 1。问题构建、热启动和轨迹结果处理也在主机侧。 [TO 调用](../examples/loco_manipulation/to_eval.py) · [Moto 求解器](../submodules/faro/src/faro/solvers/moto.py) · [Moto 构建配置](../submodules/faro/extern/moto/CMakeLists.txt) · [运行参数](../scripts/run_qwen_campaign_scene.sh)
- **轨迹验收。** 非收敛轨迹的物理复核用 NumPy、Pinocchio 和 MuJoCo `mj_forward` 在 CPU 上检查运动学、碰撞及力学量。`5481702_5` 共记录 12 次 `physical_check`，累计约 2.45 秒，嵌套在 TO 内。终态检查和评分也在 CPU 上。 [物理复核](../examples/loco_manipulation/trajectory_check.py) · [TO 终态判定](../examples/loco_manipulation/to_eval.py)

## 本地 Ollama 的推理设备

两次作业在各自节点用 Ollama 0.40.16 监听 `127.0.0.1:11434`。搜索进程向本机 OpenAI 兼容端点发请求，宿主机上的 Ollama runner 使用 `CUDA0`。两次各有 16 次 Qwen 14B 聊天调用、10 次 Qwen 7B 聊天调用和 17 次 EmbeddingGemma 调用。日志在每次装载时都记录同样的 GPU 卸载结果。 [Slurm 启动脚本](../scripts/14_qwen_campaign.sbatch) · [5481702 Hydra 配置](../results/md_qwen_campaign/move_through_clutter/job_5481702_5_ollama/.hydra/config.yaml) · [5480104 Ollama 日志](../logs/md-campaign-server-5480104.log) · [5481702 Ollama 日志](../logs/md-campaign-server-5481702.log)

| 模型 | 用途 | 两次作业的设备证据 |
| --- | --- | --- |
| `qwen2.5-coder:14b` | 主提案及代码生成重试 | `49/49` 层卸载到 GPU，`CUDA0` KV 缓冲 6,144 MiB |
| `qwen2.5-coder:7b` | 新颖性等辅助聊天调用 | `29/29` 层卸载到 GPU，`CUDA0` KV 缓冲 1,792 MiB |
| `embeddinggemma:latest` | 向量嵌入 | `25/25` 层卸载到 GPU |

两次均设置 `OLLAMA_MAX_LOADED_MODELS=1`，每次各记录 43 次模型装载。Ollama 同时保留 `CPU_Mapped` 模型缓冲和 `CUDA_Host` 缓冲，用于主机侧工作。`5481702_5` 的聊天和 embedding 请求服务时间合计约 **11 分 06 秒**，占作业墙钟约 **10.7%**。模型调用集中在短窗口，其余大段时间用于 CPU 求解。 [5481702 Ollama 日志](../logs/md-campaign-server-5481702.log)

**边界。** Slurm 两次均未提供 `gres/gpuutil` 或 `gres/gpumem`。`5480104_5` 的旧采样器传入节点全局 GPU 编号后报错，GPU 样本为 0 条，利用率和显存均值无法补采，CPU 路径只由该次阶段和代码验证。`5481702_5` 的 15 秒间隔采样给出设备级样本分布，0% 表示该样本观测值，不能据此断言两次采样之间始终无 GPU 活动、计算 GPU 活跃秒数、精确分摊逐进程 CPU/GPU 用量或确定连续显存峰值。GIN 结束时间精确到秒，HTTP 区间归属按其可用精度计算，请求含模型装载、主机开销和推理。阶段计时是墙钟，含初始化、锁等待和 I/O 等开销，嵌套阶段不能重复相加。MuJoCo 物理检查与单独的渲染、闭环跟踪和数据集再求解是不同入口，本报告只覆盖这两次搜索。两次是同一场景、同一种子，核对基于留存产物与 Slurm 查询，未提交新作业。 [5480104 采样故障复现](job_5480104_verification.md#gpu-采样故障复现与修复) · [5481702 原始样本](../logs/md-campaign-5481702_5.gpu.jsonl)
