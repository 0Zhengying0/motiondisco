# MotionDisCo 在 Karolina 的本地 Qwen 性能报告

审计日期为 2026 年 11 月 22 日，作业时间采用 Europe/Prague。可核对的复现作业运行于 11 月 16–19 日。

11 月 23 日的两次 `move_through_clutter` 性能采集核验及 CPU、GPU 时间线见 [任务 5480104 与 5481702 的 CPU 与 GPU 使用分析](jobs_5480104_5481702_gpu_cpu_analysis.md)。

## 总览

正式实验覆盖 **9 个场景、22 个 Slurm 数组任务**，包括两轮全场景、一次启动失败的 parkour 补跑以及修正后的 parkour 补跑。20 项进入搜索，共产生 **457 个提交评估的候选**，其中 20 个是初始程序，437 个是搜索提案。454 个候选留下评估记录，453 个有最终评估记录。51 个 TO 返回结果，18 个收敛，24 条达到评估器的 `to_valid` 标准，对应 20 个不同的有效接触计划。3 个场景各有两次运行产出有效轨迹。按任务结果核验，**只有 `move_through_clutter` 达成任务，两个作业各两条，共四条、三种接触计划**。另外 20 条有效轨迹涉及堆箱或跨桌搬箱，物体终态未完成描述中的搬运任务。

22 项合计消耗 **29.07 A100 分配小时、465.11 分配 CPU 核时、128.99 实际 CPU 核时**。按已发生的正式实验账单折算，每条 `to_valid` 轨迹平均占 1.21 GPU 分配小时，每条确认完成任务的轨迹占 7.27 GPU 分配小时。两项 parkour 共用了 12.88 GPU 分配小时，约占正式实验 44%，并获得零条有效轨迹。独立搜索另有 7 项，KSO 诊断 3 项，渲染 2 项，模型探针 1 项，环境与安装作业 13 项。48 项均保存在逐运行表中。 [逐运行 CSV](motiondisco_runs.csv) · [逐场景 CSV](motiondisco_scene_summary.csv) · [Slurm 账务快照](karolina_sacct.psv)

## 实验设置与运行识别

- 正式实验的启动日志逐项记录 MotionDisCo `0df8eab8623f58b447cd8402836ceffcdd472360` 与 FARO `458afa0cef22b498a68aaccb232e08942880f333`。当前仓库 `e94c24c` 提交归档了复现进度、脚本与日志。正式运行采用 Ollama 0.40.16，Qwen2.5-Coder 14B 负责主提案，7B 负责新颖性等辅助调用，embeddinggemma 用于向量检索。三个模型清单 ID 依次为 `9ec8897f747e`、`dae161e27b0e` 和 `85462619ee72`。 [启动脚本](../scripts/14_qwen_campaign.sbatch) · [正式作业样例](../logs/md-campaign-5456437_0.out)
- 正式运行使用 `legacy` 评分、默认初始条件、`island_small`／`small_budget`（4 岛、归档 20）、本地评估，每次最多一个提案和一个评估，关闭提示演化、周期性元分析和多样性评分，按场景给 11–40 个搜索节点。外层作业时限为 12 小时，本地单候选时限为 75 分钟。脚本为 KSO 接触模式上限设 50，为 TO 配置 1 个求解工作线程。独立搜索的 Hydra 配置为 2 岛、归档 40、元分析间隔 10，通常采用相同的本地模型，并以各自的任务描述和 2 或 10 个节点运行。 [预算表](../scripts/qwen_campaign.tsv) · [正式启动参数](../scripts/run_qwen_campaign_scene.sh) · [正式 Hydra 快照](../results/md_qwen_campaign/box_stacking/job_5456437_1_ollama/.hydra/config.yaml) · [独立 Hydra 快照](../results/shinka_loco_manipulation/2026.11.17082902_ollama/.hydra/config.yaml)
- `5447792` 第一轮使用默认 3 次新颖性尝试，Ollama 日志中的 `MAX_LOADED_MODELS` 为 0（自动设置）。`5453323` 是启动阶段失败的双场景补跑。`5453972` 和 `5456437` 将新颖性尝试设为 6、同时驻留模型上限设为 1。数组项用 `阵列ID_下标` 标识，实际 Slurm 作业号与 Ollama 日志通过 `JobIDRaw` 对齐。每个独立搜索由启动日志的输出目录映射，共包含 25 个搜索数据库，并对数据库中的跨岛初始程序副本去重。 [第一次补跑错误](../logs/md-campaign-5453323_6.err) · [新颖性默认值](../shinka/core/config.py) · [Slurm 快照](karolina_sacct.psv)
- 仓库的 Claude 基准启动入口与本地 Qwen 共享前述九场景节点预算和部分演化配置。Claude 入口指定 `claude-max/claude-opus-5-5`、高推理强度、32,768 最大生成 token 和本地 embedding，且以节点预算停止；本地 Qwen 作业有独立的模型、辅助调用和补跑配置。 [仓库 Claude 基准入口](../examples/loco_manipulation/run_search.sh)

## 指标口径

| 指标 | 取数规则 |
|---|---|
| 生成与完成 | 预算是包括第 0 代初始程序的候选代槽。生成数包含已提交评估的初始程序及提案，另列实际写出的代目录 `main.py` 数。评估记录按 `gen_N/results/metrics.json` 计数，最终评估排除仍有临时 `pending`／`skipped` 标记的记录。最终记录也包含程序错误、重复计划和评估器主动拒绝的候选。 |
| 接触合法与离散目标 | 对可检查的非重复计划，核对条目形状、等长渠道、足底支撑、至少两个模式、接触面切换前经过空接触，并计入 FARO 转换时发现的非法接触。离散目标 `goal_match` 另计，只测试计划的末接触模式是否满足配置，空目标也可能为真。`contact_gate_pass` 记录已进入 KSO／分段 TO 路径的候选，便于区分静态统计口径与运行时筛选。 |
| KSO 与 TO | KSO 通过取 `ik_feasible=true`。普通路径代表全计划运动学可行，增量配置可用首个可行窗口作为 KSO 信号。TO 发起、返回、数值收敛分别计数。返回的 `to_converged` 取求解器收敛标志，单次求解以返回状态为 0 判定。 |
| 物理有效与评分 | `to_valid` 需满足求解器收敛或附加物理检查通过，且通过适用的硬终端目标。独立列出 `to_physical.pass`，主要用于非收敛解。正式实验的 24 条 `to_valid` 中，18 条收敛、6 条由物理检查接受。默认 `legacy` 在 `to_cost>0` 时取 `1/(1+to_cost)`，否则为 0；TO Cost 为 `100 × 约束违反总量 / TO 节点数 + 0.01 × jerk 代价 / 接触模式数`。51 次非零评分包含 27 次未达有效标准的 TO。 |
| 任务达成 | 对有效轨迹使用可得的连续终态证据。穿越障碍用 FARO 的末端机器人位置目标与 `to_goal.met`。堆箱按 FARO `box_stack_height` 公式读取保存轨迹的始末姿态，并检查箱体位移；跨桌搬箱读取白箱始末位置。未找到有效轨迹的运行记录为 `no_usable_trajectory`。 |
| 最佳轨迹 | 在每个作业内按 `combined_score` 选取 `to_valid=true` 的最高分候选，同分取最早代。逐运行 CSV 另给出全部 TO 返回结果中的最高分及其有效标志。场景汇总里的不同有效接触计划按完整接触计划内容去重。 |

[评估流程](../examples/loco_manipulation/evaluate.py) · [评分实现](../examples/loco_manipulation/scoring.py) · [TO 实现](../examples/loco_manipulation/to_eval.py) · [接触检查](../examples/loco_manipulation/plan_checks.py) · [物理检查](../examples/loco_manipulation/trajectory_check.py)

## 正式实验的逐场景结果

墙钟与内存范围使用进入评估的作业，累计 GPU 和 CPU 小时纳入同一场景的全部尝试。GPU 小时表示资源分配，CPU 核时取 `TotalCPU`。RSS 取 `.batch` 步骤的 `MaxRSS`。

| 场景 | 作业 | 最终评估 | 接触合法／KSO／TO 收敛 | 有效／去重计划 | 任务达成 | 单次墙钟 h | GPU h 合计 | CPU 核时合计 | 峰值 RSS GiB 范围 | LLM 请求 h | KSO 诊断 h |
|---|---:|---:|---|---|---:|---|---:|---:|---|---:|---:|
| banana_real | 2 | 54 | 28/0/0 | 0/0 | 0 | 1.12–1.74 | 2.87 | 10.26 | 16.7–22.3 | 0.55 | 2.13 |
| box_stacking | 2 | 22 | 9/9/5 | 6/6 | 0 | 0.25–2.61 | 2.86 | 6.50 | 21.9–27.4 | 0.28 | — |
| climb_table_up_down_with_box | 2 | 42 | 14/14/10 | 14/11 | 0 | 0.71–0.85 | 1.56 | 11.75 | 4.1–37.3 | 0.74 | 0.08 |
| climb_table_with_box | 2 | 26 | 4/1/0 | 0/0 | 0 | 0.14–0.73 | 0.88 | 6.82 | 7.1–19.7 | 0.42 | — |
| long_dist_pick_place | 2 | 40 | 9/6/0 | 0/0 | 0 | 1.23–1.96 | 3.19 | 9.76 | 10.7–23.4 | 0.46 | 0.06 |
| move_through_clutter | 2 | 29 | 16/17/3 | 4/3 | 4 | 1.32–2.92 | 4.23 | 10.32 | 7.7–22.7 | 0.42 | — |
| parkour_pick_place_1 | 4 | 114 | 2/0/0 | 0/0 | 0 | 1.24–4.24 | 6.83 | 42.01 | 7.8–121.2 | 2.70 | 0.31 |
| parkour_pick_place_2 | 4 | 98 | 14/5/0 | 0/0 | 0 | 1.11–3.27 | 6.05 | 26.80 | 14.6–37.3 | 1.60 | 1.29 |
| under_table_pick_place | 2 | 28 | 4/0/0 | 0/0 | 0 | 0.15–0.45 | 0.60 | 4.76 | 3.7–10.3 | 0.31 | 0.20 |

- **穿越障碍 `move_through_clutter`** 两轮均产出两条达标轨迹。第一轮 g7、g13，第二轮 g5、g11；机器人终态位置与目标的距离范数约 0.142–0.151 m，场景按目标坐标分量的 0.10 m 容差加 0.05 m 求解余量判定。12 个返回的无效 TO 与 1 个临时 TO 记录是进一步提高产量的主要损耗。 [场景终态目标](../submodules/faro/src/scenes/motiondisco/move_through_clutter/goals.py) · [逐运行任务证据](motiondisco_runs.csv)
- **堆箱 `box_stacking`** 两个正式作业各有 3 条有效轨迹，单次耗时 0.25–2.61 h。六条轨迹的最高箱顶始末均约为 1.10 m，箱体终态几乎与起点重合。该场景表现为可产出物理有效运动，现有轨迹的堆叠高度没有增加。独立烟测的五条有效轨迹也有同样结果。 [堆箱评分](../submodules/faro/src/scenes/motiondisco/box_stacking/goals.py) · [堆箱初始条件](../submodules/faro/src/scenes/motiondisco/box_stacking/initial_conditions.py)
- **跨桌搬箱 `climb_table_up_down_with_box`** 每轮 7 条有效，是物理产量最高的场景。14 条有效轨迹里白箱终态均仍在初始坐标 `(0.4, 0.1, 0.135) m`，桌子沿 x 轴覆盖约 0.65–1.35 m。该场景的离散约束只要求机器人两脚和白箱在地面，内置 outcome scorer 返回常数 0。两轮最佳物理轨迹的分数与 TO Cost 完全相同，均未完成搬箱。 [跨桌目标与评分](../submodules/faro/src/scenes/motiondisco/climb_table_up_down_with_box/goals.py) · [桌体尺寸](../submodules/faro/src/scenes/motiondisco/climb_table_up_down_with_box/scene.py) · [起点](../submodules/faro/src/scenes/motiondisco/climb_table_up_down_with_box/initial_conditions.py)
- **抓香蕉 `banana_real`** 两轮共 28 个候选进入且未通过 KSO，18 个重复计划，零 TO。KSO 失败诊断累计 2.13 h，是该场景 2.87 h 总分配墙钟里的大项。**登桌持箱**和**桌下取箱**的主要损耗更早，集中在离散末接触和接触转换。登桌持箱有一次 TO 的连续终端目标达标（`5456437_2` g11），该次轨迹因物理检查超限未达到 `to_valid`。 [FARO 场景目标](../submodules/faro/src/scenes/motiondisco/climb_table_with_box/goals.py) · [该候选 extra.json](../results/md_qwen_campaign/climb_table_with_box/job_5456437_2_ollama/gen_11/results/extra.json)
- **远距离抓放 `long_dist_pick_place`** 共 6 个 KSO 通过并返回 TO，6 个均未达到物理标准，也均未达到保存的末端位置目标。**parkour 1** 在 114 份最终评估里只有 2 份接触合法，零 KSO 通过。**parkour 2** 的 98 份最终评估有 5 份通过 KSO，五个 TO 全部物理无效且终端目标未达。两项 parkour 合计有 126 个候选的主要失败归为接触不合法，多次补跑仍卡在接触计划与动力学阶段。 [逐场景汇总](motiondisco_scene_summary.csv) · [逐运行失败记录](motiondisco_runs.csv)

## 正式实验的逐运行账单

`预算／生成／记录／最终` 中的生成包含初始程序。末列为最佳有效轨迹的代数、评分与 TO Cost。逐作业的起止时间、模型、完整配置和资源字段见逐运行 CSV。

| Slurm 数组项 | 场景 | 预算／生成／记录／最终 | 接触合法／KSO／TO 收敛／有效／达成 | 墙钟 h | CPU 核时 | 峰值 RSS GiB | 最佳有效代／评分／TO Cost |
|---|---|---|---|---:|---:|---:|---|
| 5447792_0 | banana_real | 27/27/27/27 | 16/0/0/0/0 | 1.74 | 5.33 | 22.25 | — |
| 5447792_1 | box_stacking | 11/11/11/11 | 6/6/2/3/0 | 2.61 | 4.53 | 27.43 | g9 / 0.0711482 / 13.0552 |
| 5447792_2 | climb_table_with_box | 13/13/13/13 | 1/0/0/0/0 | 0.14 | 1.77 | 7.11 | — |
| 5447792_3 | climb_table_up_down_with_box | 21/21/21/21 | 7/7/6/7/0 | 0.85 | 6.27 | 37.27 | g5 / 0.322927 / 2.09667 |
| 5447792_4 | long_dist_pick_place | 20/20/20/20 | 3/2/0/0/0 | 1.23 | 5.48 | 23.43 | — |
| 5447792_5 | move_through_clutter | 15/15/15/15 | 9/9/1/2/2 | 2.92 | 5.58 | 22.69 | g7 / 0.044526 / 21.4588 |
| 5447792_6 | parkour_pick_place_1 | 40/38/35/35 | 1/0/0/0/0 | 4.24 | 13.81 | 121.25 | — |
| 5447792_7 | parkour_pick_place_2 | 34/30/30/30 | 3/1/0/0/0 | 1.11 | 7.78 | 37.29 | — |
| 5447792_8 | under_table_pick_place | 14/14/14/14 | 1/0/0/0/0 | 0.15 | 1.86 | 10.26 | — |
| 5453323_6 | parkour_pick_place_1 | 40/0/0/0 | 0/0/0/0/0 | 0.02 | 0.00 | 0.72 | — |
| 5453323_7 | parkour_pick_place_2 | 34/0/0/0 | 0/0/0/0/0 | 0.01 | 0.00 | 0.72 | — |
| 5453972_6 | parkour_pick_place_1 | 40/40/40/40 | 1/0/0/0/0 | 1.34 | 13.72 | 18.11 | — |
| 5453972_7 | parkour_pick_place_2 | 34/34/34/34 | 4/1/0/0/0 | 1.66 | 8.47 | 19.66 | — |
| 5456437_0 | banana_real | 27/27/27/27 | 12/0/0/0/0 | 1.12 | 4.93 | 16.67 | — |
| 5456437_1 | box_stacking | 11/11/11/11 | 3/3/3/3/0 | 0.25 | 1.97 | 21.93 | g3 / 0.0844513 / 10.8411 |
| 5456437_2 | climb_table_with_box | 13/13/13/13 | 3/1/0/0/0 | 0.73 | 5.06 | 19.69 | — |
| 5456437_3 | climb_table_up_down_with_box | 21/21/21/21 | 7/7/4/7/0 | 0.71 | 5.48 | 4.12 | g1 / 0.322927 / 2.09667 |
| 5456437_4 | long_dist_pick_place | 20/20/20/20 | 6/4/0/0/0 | 1.96 | 4.28 | 10.66 | — |
| 5456437_5 | move_through_clutter | 15/15/15/14 | 7/8/2/2/2 | 1.32 | 4.74 | 7.66 | g11 / 0.044526 / 21.4588 |
| 5456437_6 | parkour_pick_place_1 | 40/39/39/39 | 0/0/0/0/0 | 1.24 | 14.48 | 7.84 | — |
| 5456437_7 | parkour_pick_place_2 | 34/34/34/34 | 7/3/0/0/0 | 3.27 | 10.55 | 14.58 | — |
| 5456437_8 | under_table_pick_place | 14/14/14/14 | 3/0/0/0/0 | 0.45 | 2.90 | 3.69 | — |

`5447792`、`5453972`、`5456437` 分别用 15.00、3.00、11.05 GPU 分配小时，产出 12、0、12 条有效轨迹。两轮全场景各确认两条完成任务。其余 76 秒属于 `5453323` 的两项启动失败。旧汇总的 11 行覆盖第一轮和修正后的 parkour 补跑，原表把有有效轨迹的场景标为 `scene_success`。 [历史汇总](../results/qwen_campaign_summary.csv) · [完整逐运行 CSV](motiondisco_runs.csv)

## 失败与中断

- **算法与候选主失败**共 436 项，按每代主要原因计一次。接触不合法 220，重复接触计划 84，KSO 不可行 36，候选代码错误 27，返回的 TO 无效 27，计划过短 20，离散目标不匹配 13，新颖性尝试耗尽 7，模式数超限 2。接触合法性单项检查覆盖 341 份记录，其中 100 份合法、241 份不合法；主失败会优先使用过短等具体原因。运行时另有 165 次接触面切换规则拒绝、12 次 FARO 接触转换错误（10 次末端接触元组形状错误、2 次物体自接触目标）。候选程序错误包括未定义名称、缩进错误和无效的字典键。七次未获准提交的提案均记录为 `NOT_NOVEL`，分别为 `5447792_6` 两次、`5447792_7` 四次、`5456437_6` 一次。 [逐运行失败计数与原始错误](motiondisco_runs.csv)
- **无效 TO 的物理检查**中，穿透 26、接触间隙 25、动力学力不一致 25、接触滑移 24、关节位置超限 24、摩擦不足 11、功率超限 6、负法向力 4，同一轨迹可出现多项。远距离抓放的 TO 还存在明显终点偏差。 [物理检查](../examples/loco_manipulation/trajectory_check.py) · [逐运行物理标志](motiondisco_runs.csv)
- **调度和运行故障**包括 1 次整作业内存溢出和 2 次 Hydra 启动失败。OOM 作业是 `5447792_6`（实际作业号 `5449803`），墙钟 4.24 h，RSS 121.25 GiB。其 38 个提交评估的代中，g16、g36、g39 缺少 metrics；g16、g39 的评估记录约 74 分钟，g36 约 50 分钟。调度器配置为 75 分钟，前两次列为接近时限的中断。另有 `5456437_5` g9 在 TO 留下临时记录，数据库的评估时长约 52 秒。正式任务共有 4 次候选评估中断；Slurm 作业状态中确认的整作业 TIMEOUT 为 0。两个 Hydra 故障均发生在搜索前，涉及严格配置覆写语法。 [OOM 日志](../logs/md-campaign-5447792_6.err) · [启动失败日志](../logs/md-campaign-5453323_6.err) · [本地调度器](../shinka/launch/scheduler.py)
- **运行完成率**按 Slurm 口径为 19/22 作业 `COMPLETED`。按最终评估和节点预算，16/22 达满，2 次因提案不足未达预算，1 次因临时评估记录未达预算，其余分别为两次启动失败及一次 OOM。 [逐运行状态](motiondisco_runs.csv)

## 资源和分阶段耗时

- 作业脚本写 8 CPU；`sacct` 的正式作业均为 **16 CPU、1 GPU、124160 MiB 请求内存（121.25 GiB）**。Ollama 日志识别到 NVIDIA A100-SXM4-40GB。正式作业的实际 CPU 用量摊到墙钟约为 4.44 核，约占分配核时的 27.7%；评估作业的峰值 RSS 中位数为 18.88 GiB。单 GPU、单候选评估的资源开销会随具体提案变化。例如堆箱两轮均产出 3 条有效轨迹，墙钟从 2.61 h 到 0.25 h，实际 CPU 从 4.53 到 1.97 核时。 [Slurm 账务](karolina_sacct.psv) · [Ollama 设备日志](../logs/md-campaign-server-5456438.log)
- LLM 聊天端点累计 **1,212 次请求、7.48 请求小时**，embedding 累计 **633 次、0.48 请求小时**。这些值累计每条 Ollama HTTP 记录的服务时间，含模型装载、辅助调用等，任务同一时段可能在评估其他候选。数据库中有效代记录的提案阶段累计 7.97 h，评估流水线累计 20.61 h。候选 Python 函数自身累计 237.98 s，取 `execution_time_mean`。已记录的 48 次 KSO 失败诊断累计 **4.07 h**。 [Ollama 请求样例](../logs/md-campaign-server-5456438.log) · [流水线阶段定义](../shinka/core/pipeline_timing.py) · [KSO 诊断计时](../examples/loco_manipulation/ik_eval.py)
- parkour 1 在将模型驻留数设为 1 并增加新颖性尝试后，两次评估作业的峰值 RSS 分别为 18.11 GiB 和 7.84 GiB，低于首次的 121.25 GiB，仍产出零条有效轨迹。第二轮该场景的 147 次聊天请求用时 3,801.83 s，而评估流水线只记录 247.29 s，提案和模型服务是这次作业的主要成本。parkour 2 第二轮的评估流水线占 9,422.00 s，同时有 2,902.2 s 的 KSO 诊断。 [补跑配置](../scripts/14_qwen_campaign.sbatch) · [逐运行计时](motiondisco_runs.csv)

## 独立搜索、诊断和渲染

以下作业单独结算。独立搜索使用其自有的任务描述和搜索预算，诊断重复评估已有的 `example_scene` g4。模型探针 `5441282` 验证 Qwen 响应及 768 维 embedding，用时 283 s。环境与安装的 13 项作业在 CSV 归入 `setup`，其中 5 项失败，涉及 CMake／编译工具、归档解包和 t_renderer 的 GLIBC 兼容性。 [复现进度](../docs/karolina_reproduction_progress.md) · [作业清单](motiondisco_runs.csv)

| Job ID | 场景／用途 | 预算 | 最终评估／KSO／收敛／有效 | 墙钟 s | CPU 核时 | 峰值 RSS GiB | 结果 |
|---|---|---:|---|---:|---:|---:|---|
| 5441633 | example_scene | 2 | 0/0/0/0 | 41 | 0.002 | 0.72 | Hydra 解析失败，找不到 `examples` |
| 5441647 | example_scene | 2 | 1/0/0/0 | 77 | 0.145 | 6.97 | API 成本上限为 0，初始候选后提前停止 |
| 5441689 | example_scene | 2 | 2/0/0/0 | 156 | 0.430 | 16.30 | 两条记录分别为初始计划和离散目标未匹配 |
| 5443185 | example_scene | 10 | 9/0/0/0 | 626 | 2.018 | 22.71 | g8 新颖性耗尽，g4 的 t_renderer 构建路径出错 |
| 5443507 | example_scene | 10 | 10/3/0/0 | 3,939 | 3.695 | 36.48 | 3 个 TO 均未通过物理检查，最高 TO 分为 g8，0.000747288，Cost 1,337.17 |
| 5446276 | box_stacking | 10 | 0/0/0/0 | 21 | 0.001 | 0.68 | 场景描述的 shell 引号导致错误的工作目录 |
| 5446377 | box_stacking | 10 | 10/5/4/5 | 6,605 | 4.396 | 37.43 | 最佳 g9，评分 0.0412424，TO Cost 23.2469；五条的堆叠任务均未达成 |
| 5443431 | example_scene KSO 诊断 | — | 1/0/0/0 | 61 | 0.013 | 1.00 | 缺少 `make` |
| 5443492 | example_scene KSO 诊断 | — | 1/0/0/0 | 38 | 0.007 | 2.25 | 环境安装 `make` 后，计划因重复被短路 |
| 5443495 | example_scene KSO 诊断 | — | 1/0/0/0 | 352 | 0.370 | 2.14 | 重新评估 g4，KSO 前缀在 mode 4 首次不可行（前缀长度口径） |
| 5446847 | box_stacking 渲染 | — | — | 2 | 0.0001 | 0.07 | 缺少 `_run_common` 的导入路径 |
| 5446851 | box_stacking 渲染 | — | — | 8 | 0.002 | 1.20 | 从 301 个 qpos 样本输出 575 帧，640×480、30 fps |

[独立烟测日志](../logs/md-box-smoke-5446377.out) · [KSO 诊断结果](../logs/md-kso-retest-5443495.out) · [渲染日志](../logs/md-render-5446851.out) · [已存轨迹视频](../results/shinka_loco_manipulation/2026.11.17082902_ollama/best/results/to_run.mp4)

## 面向自动场景生成和数据生产的结论

在本次预算下，`move_through_clutter` 是唯一已有可核验任务轨迹的场景，累计 4.23 GPU 分配小时、10.32 CPU 核时得到 4 条。跨桌搬箱和堆箱的有效产量分别为 14 和 6 条，箱体终态暴露出任务目标覆盖不足。香蕉受 KSO 可行性制约，登桌和桌下任务较早消耗在接触和离散目标，远距离抓放与 parkour 2 进一步受长计划的动力学与终点偏差制约。parkour 1 同时表现出高提案成本、接触转换失败与一次主机内存溢出。若目标是生成带任务标签的轨迹，产能应依据可核验任务达成数计算；按有效轨迹数量估计产能会将这批正式结果的可用样本从 4 条放大至 24 条。

## 重新生成统计表

在 MotionDisCo 根目录执行下述只读提取命令。第一行使用随报告保存的账务快照。新作业完成后，本机账务可用时使用第二行更新快照，并重新生成两张 CSV。

```bash
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py --refresh-sacct
```

[提取脚本](extract_motiondisco_performance.py) · [逐运行 CSV](motiondisco_runs.csv) · [逐场景 CSV](motiondisco_scene_summary.csv) · [原始 Slurm 摘录](karolina_sacct.psv)

**边界与后续防御性工作。** 本报告只读取已有文件和 Slurm 账务，离线计算保存轨迹的终态统计，未重跑 MotionDisCo、渲染或提交 GPU 作业。时间范围为截至审计日的仓库产物和可定位账务，数值 0 表示记录中观察到零次，空白或“—”表示无法获取或不适用。独立作业缺少逐项 Git 版本打印；所有已保存 Hydra 快照、启动参数及可见模型采样记录均未给出逐次运行种子，评估 wrapper 的通用种子分支也被本任务的空参数回调覆盖，因此不同 Job ID 不足以证明独立随机种子。原始账务未记录 GPU 利用率或峰值显存，模型请求时间含模型服务开销且可与评估重叠；完整 KSO、TO 和渲染函数耗时无法获取，KSO 诊断、评估流水线与渲染作业的 8 秒墙钟各按实测口径呈现；两次接近单候选时限的中断无明确退出原因，OOM 后的内存下降亦无法单独归因于某一个配置改动。四条任务达成依据保存轨迹与场景终态检查，未做闭环跟踪或实机复验；堆箱和跨桌搬箱的离线失败判定使用 1 cm 始末不变容差，保留原始高度与位移，后续有实际位移的轨迹需按场景定义确认完成。样本量、配置和模型差异限制了场景间因果比较以及与 Claude 的直接性能对照。未来规模化生产可降低这些不确定性的方法包括持久化种子与模型请求配置、记录求解阶段边界和退出原因、将场景终态与任务评分纳入验收、保存逐进程和 GPU 遥测，以及在提交求解前检查接触计划并按计划长度或候选难度分档。
