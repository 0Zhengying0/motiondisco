# MotionDisco：Karolina 复现进度

目标：使用 Karolina 本地 Qwen 运行 MotionDisco，得到并评估有效运动轨迹。

## 已完成

- 建立 Apptainer/Conda 环境，安装 Acados、Moto、FARO、MotionDisco，补齐 `make` 和 `t_renderer`。
- 部署 Ollama、Qwen 14B/7B 和 embeddinggemma；模型调用测试通过。
- `example_scene` 试跑完成：10 代中 3 个候选进入 TO，均未通过物理检查。
- `box_stacking` 10 代搜索（作业 `5446377`）完成：5 个候选通过物理检查，其中 4 个 TO 收敛；最佳结果为第 9 代。
- 最佳轨迹已渲染为 [`to_run.mp4`](../results/shinka_loco_manipulation/2026.11.17082902_ollama/best/results/to_run.mp4)（作业 `5446851`，640×480，575 帧）。

## 9 场景实验（`5447792`）

- `_0`～`_8` 均已结束；7 个场景达到节点预算。
- 3 个场景产生有效轨迹，共 12 条：`box_stacking` 3 条、`climb_table_up_down_with_box` 7 条、`move_through_clutter` 2 条。
- 其余 6 个场景暂未找到有效轨迹。其中 `_6 parkour_pick_place_1` 在 35/40 个有评估结果的节点后内存溢出（Slurm `OUT_OF_MEMORY`，峰值约 127 GB）；`_7 parkour_pick_place_2` 正常结束，但只得到 30/34 个节点的评估结果。日志显示缺失节点由候选计划在新颖性检查中被拒绝、提案重试耗尽造成。
- 已调整补跑配置：Ollama 同时最多加载 1 个模型，提案新颖性重试次数从 3 提高到 6。`--mem=0` 提交被 Slurm 拒绝；下一次只补跑 `_6`、`_7`，使用原有可提交的资源请求，验证减少模型驻留内存后的效果。
- 补跑作业 `5453323` 的两个数组项均因 Hydra 参数写法错误在搜索前退出；已修正为 `++evo_config.max_novelty_attempts=6`，并通过实际配置解析检查。
- [实验配置](qwen_campaign.md)；[场景与预算表](../scripts/qwen_campaign.tsv)；[逐场景结果汇总表](../results/qwen_campaign_summary.csv)。

## 待确定的实验细节

- 每个场景做几次独立重复运行。
- 是否在当前 `legacy` 评分之外增加 `quality` 或多样性实验。
- 最终报告比较哪些指标：场景成功率、有效轨迹数、耗时、轨迹质量。

## 接下来的工作

1. 补跑 `_6`、`_7`，核查内存和节点完成数。
2. 确定独立重复次数并补跑，形成复现报告。
