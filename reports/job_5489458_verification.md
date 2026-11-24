# Karolina 作业 5489458 端到端核验

`5489458` 于 2026 年 11 月 24 日 15:19:04–15:57:32（Europe/Prague）在 `acn06` 完成，Slurm 状态为 `COMPLETED`，退出码为 `0:0`。Qwen 在第 2 次尝试生成通过 MuJoCo 验证的场景。MotionDisCo 用默认初始程序完成 10 代评估，产出 **3 条独立验收通过的轨迹**。三条的 G1 终点误差均约 **0.87 cm**，验收上限为 **10 cm**。 [作业日志](../results/md-qwen-generate-5489458.out) · [工作流结果](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/result.json) · [Slurm 账务](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/karolina_sacct.psv)

## 场景生成与验证

场景注册为 `generated.qwen_261124_141926_7o3bcm5w`。地面为 6 × 4 m，G1 从平面坐标 `(1.5, 1.0)` 走向 `(-1.0, 1.5)`，水平距离为 2.550 m。两张短平台分别支撑一个绿箱和一个黄箱。初始回答把箱体的支撑面写成 `surface`，验证器对两个箱体返回 `INVALID_SUPPORT_SURFACE`。第二次请求的 Prompt 包含第一次回答和这两项错误。Qwen 把支撑面改为 `top`，MuJoCo 3.13.0 验收通过。2 s 静置仿真中，两个箱体的最大位置漂移均约 0.175 mm。最终 SceneSpec 与注册目录中的快照一致。 [第一次验证](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/attempt_01/validation.json) · [第二次 Prompt](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/attempt_02/prompt.txt) · [最终场景](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/scene_spec.json) · [通过的验证报告](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/validation.json)

## MotionDisCo 搜索配置与结果

Hydra 快照使用 `examples/loco_manipulation/initial.py`、`legacy` 评分、`ollama_local`、`island_small` 和 `small_budget`，提案与评估并发各为 1。第 0 代 `main.py` 与仓库的 `initial.py` 逐字节相同，SHA-256 为 `e84285b28fce6210b7ffc87967bbb46d69d87f25c3fafec10490f576203b9d40`。它生成 1 个接触模式，评估得分为 0。第 1、5、8 代合格轨迹均来自随后的搜索提案。场景加载适配保留注册的资产接触权限。 `reach_position` 的 TO 每轴目标容差为 5 mm，搜索结束后按三维距离 10 cm 做独立验收。 [Hydra 配置](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/.hydra/config.yaml) · [第 0 代程序](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_0/main.py) · [任务目录快照](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/task_catalog.json)

10 代均有最终评估。5 个接触计划通过 KSO 并运行 TO，其中 3 个收敛并通过物理及终态验收。第 2、7 代的 TO 未收敛，输出未通过动力学、接触间隙、滑移和关节位置检查。其余包括 3 个重复接触计划、1 个候选程序参数错误和第 0 代的单模式计划。 [逐代 CSV](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/motiondisco_candidate_performance.csv)

| 代 | 接触模式／轨迹节点 | Legacy 分数 | 独立复算的终点误差 | 验收与保存轨迹 |
| --- | ---: | ---: | ---: | --- |
| 1 | 8／161 | 0.060940 | 0.8662 cm | [验收](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_1/results/acceptance.json) · [轨迹](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_1/results/to_run.pkl) |
| 5 | 10／201 | 0.058759 | 0.8657 cm | [验收](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_5/results/acceptance.json) · [轨迹](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_5/results/to_run.pkl) |
| 8 | 9／181 | 0.053110 | 0.8658 cm | [验收](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_8/results/acceptance.json) · [轨迹](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/gen_8/results/to_run.pkl) |

三条去重后的轨迹均用保存的数值状态重新运行了物理检查。三条的终态接触计划均为双足在地，两箱全程保持各自的支撑通道，箱体始末位置无位移。G1 基座实际终点均约为 `(-0.995, 1.495, 0.770) m`。物理结果来自保存轨迹的离线复核。第 1 代是 Legacy 评分最高的合格轨迹，第 5 代的终点误差最小。 [物理检查实现](../examples/loco_manipulation/trajectory_check.py) · [逐运行任务证据](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/motiondisco_runs.csv)

## 资源、耗时和复现记录

| 项目 | 作业记录 |
| --- | --- |
| CPU 与主机内存 | 墙钟 2,308 s。分配 16 个 CPU，使用 8,734 CPU 秒，平均使用 3.78 核。批作业峰值 RSS 为 31.03 GiB。 [Slurm 账务](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/karolina_sacct.psv) |
| GPU | 分配 1 张 A100-SXM4-40GB，折合 0.641 GPU 分配小时。每 5 秒采样，共 461 条，采样器未报告错误。利用率样本均值 6.01%，观测峰值 100%。显存样本均值 3,972 MiB，观测峰值 15,109 MiB。 [GPU 采样](../results/md-qwen-generate-5489458.gpu.jsonl) |
| Ollama 请求 | 场景生成 2 次、43.48 s，搜索聊天 16 次、355.05 s，embedding 12 次、52.64 s。三类请求均无 HTTP 错误。 [Ollama 日志](../results/md-qwen-generate-server-5489458.log) · [逐运行 CSV](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/motiondisco_runs.csv) |
| 搜索与验收阶段 | 提案累计 415.21 s，候选评估累计 1,684.85 s。评估内 KSO 累计 230.74 s，TO 累计 1,447.72 s。第 1 代的 TO 构建耗时 785.66 s。工作流结束前的独立轨迹验收耗时 0.49 s，所有已记录计时区间均已闭合。 [逐代 CSV](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/motiondisco_candidate_performance.csv) · [工作流计时](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/scene_generation_performance.jsonl) |
| 复现配置 | 场景生成种子依次为 `20261123`、`20261124`，搜索基础种子为 `20261123`。Ollama 0.40.16 使用 Qwen2.5-Coder 14B、7B 和 EmbeddingGemma。MotionDisCo 提交为 `cd401aae022956ea24404126457df6da7aed87cf`，运行时有工作区变更，阶段事件保留对应 SHA-256。FARO 提交为 `458afa0cef22b498a68aaccb232e08942880f333`。 [运行配置与源码指纹](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/motiondisco/run_performance.jsonl) · [模型完整 digest](../results/md-qwen-generate-5489458.performance.jsonl) |

GPU 指标为设备级采样均值和观测峰值。TO 构建和优化时间包含在 TO 总时间内，KSO 和 TO 包含在候选评估时间内。逐运行、逐场景、逐候选 CSV 与账务快照保存在作业目录的 `audit/` 中。 [逐场景 CSV](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/audit/motiondisco_scene_summary.csv)
