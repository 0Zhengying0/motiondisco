# MotionDisco：Karolina 复现进度

使用 Karolina 本地 Qwen 复现 MotionDisco，并评估生成的运动轨迹。截至 2026 年 11 月 24 日的作业 `5490294`，已记录 59 项 Slurm 作业，数组按子任务计数。

## 九场景复现

九场景的复现指标统一取最后一批全量运行 `5456437_0`～`5456437_8`。九个作业均为 `COMPLETED`，合计完成 **193/195** 个最终评估。`_5` 第 9 代留下 TO 临时记录，`_6` 有一次新颖性重试耗尽，两场景各少一个最终评估。该批共消耗 **11.05 A100 分配小时**，三个场景产出 **12 条 `to_valid` 轨迹**，其中 `move_through_clutter` 的两条有达成场景任务的证据。按作业号筛选逐运行 CSV 可复核这些数字。历史性能报告中的跨批合计用于追溯全部尝试与资源支出。[实验配置](qwen_campaign.md) · [逐运行 CSV](../reports/motiondisco_runs.csv) · [历史性能报告](../reports/motiondisco_performance_report.md)

| 作业 | 场景 | 最终评估／预算 | 有效轨迹 | 达成任务 |
| --- | --- | ---: | ---: | ---: |
| `5456437_0` | `banana_real` | 27/27 | 0 | 0 |
| `5456437_1` | `box_stacking` | 11/11 | 3 | 0 |
| `5456437_2` | `climb_table_with_box` | 13/13 | 0 | 0 |
| `5456437_3` | `climb_table_up_down_with_box` | 21/21 | 7 | 0 |
| `5456437_4` | `long_dist_pick_place` | 20/20 | 0 | 0 |
| `5456437_5` | `move_through_clutter` | 14/15 | 2 | 2 |
| `5456437_6` | `parkour_pick_place_1` | 39/40 | 0 | 0 |
| `5456437_7` | `parkour_pick_place_2` | 34/34 | 0 | 0 |
| `5456437_8` | `under_table_pick_place` | 14/14 | 0 | 0 |

### 早期全量运行与补跑

| 作业 | 运行结果 | 记录用途 |
| --- | --- | --- |
| `5447792_0`～`5447792_5`、`5447792_8` | 七项均为 `COMPLETED`，达到各自评估预算。 | 第一轮重复结果，仅存档。[历史汇总](../results/qwen_campaign_summary.csv) |
| `5447792_6`（实际作业号 `5449803`） | `parkour_pick_place_1` 在 35/40 个最终评估后 `OUT_OF_MEMORY`，峰值 RSS 121.25 GiB。 | 保留为主机内存溢出的排障证据。[OOM 日志](../logs/md-campaign-5447792_6.err) · [Slurm 账务](../reports/karolina_sacct.psv) |
| `5447792_7` | `parkour_pick_place_2` 为 `COMPLETED`，4 次提案因新颖性重试耗尽，最终评估为 30/34。 | 保留为单独补跑的背景。[作业日志](../logs/md-campaign-5447792_7.out) |
| `5453323_6`、`5453323_7` | 两项均为 `FAILED`。Hydra 配置覆写错误，搜索未启动。 | 记录补跑启动失败，后续使用 `++evo_config.max_novelty_attempts=6`。[启动日志](../logs/md-campaign-5453323_6.err) |
| `5453972_6`、`5453972_7` | 两项均为 `COMPLETED`。单模型驻留和 6 次新颖性重试的配置下，两项分别完成 40/40、34/34 个评估，均为 0 条有效轨迹。`_6` 的峰值 RSS 为 18.11 GiB。 | 保留为 OOM 与预算不足之后的单独补跑记录。[逐运行 CSV](../reports/motiondisco_runs.csv) |

另有一次 `--mem=0` 提交被 Slurm 拒绝，属于提交记录，未产生运行结果。

## 环境、烟测与性能采集

Apptainer/Conda 环境、Acados、Moto、FARO、MotionDisco、Ollama 和本地模型均已部署。以下作业记录安装、功能验证、故障诊断和性能采集过程。

| 作业 | 运行结果与用途 |
| --- | --- |
| `5440754`、`5440827`、`5440829`、`5440854`、`5440856` | 均为 `COMPLETED`，分别完成环境创建及 Acados、Moto、FARO、MotionDisco 安装。[Slurm 账务](../reports/karolina_sacct.psv) |
| `5440824`、`5440825`、`5440826` | Acados 构建均为 `FAILED`，第一项缺少 CMake，后两项缺少构建工具和编译器。[构建日志](../logs/md-acados-5440825.err) |
| `5440864`、`5440866`、`5440881`、`5441282` | 首次 Ollama 安装因 `tar --zstd` 不受支持而 `FAILED`。修正安装、拉取模型和模型调用探针均为 `COMPLETED`，验证了 Qwen 响应和 768 维 embedding。[安装日志](../logs/md-ollama-install-5440864.err) · [探针日志](../logs/md-llm-test-5441282.out) |
| `5441633`、`5441647`、`5441689`、`5443185`、`5443507` | `example_scene` 烟测。首项因模块导入失败而 `FAILED`。其余均为 `COMPLETED`，依次留下 1、2、9、10 个最终评估。最后一次有 3 个候选进入 TO，均未达到有效标准。[独立搜索记录](../reports/motiondisco_performance_report.md) |
| `5443298`、`5443405` | `t_renderer` 安装先因 GLIBC 兼容性 `FAILED`，换用兼容版本后 `COMPLETED`。[首次安装日志](../logs/md-tera-5443298.err) · [修正安装日志](../logs/md-tera-5443405.out) |
| `5443431`、`5443492`、`5443495` | KSO 排障均为 `COMPLETED`。同一 `example_scene` 候选先遇到缺少 `make` 和重复计划短路，最后定位到 mode 4 首次不可行。[最终排障日志](../logs/md-kso-retest-5443495.out) |
| `5446276`、`5446377` | `box_stacking` 烟测首项因场景描述的 shell 引号 `FAILED`。第二项 `COMPLETED`，10 代产生 5 条有效轨迹，4 条 TO 收敛，最高分为第 9 代，5 条均未达成堆箱任务。[烟测日志](../logs/md-box-smoke-5446377.out) · [终态记录](../reports/motiondisco_performance_report.md) |
| `5446847`、`5446851` | 首次渲染因导入路径 `FAILED`，修正后 `COMPLETED`，输出最高分轨迹的视频（640×480，575 帧）。[视频](../results/shinka_loco_manipulation/2026.11.17082902_ollama/best/results/to_run.mp4) |
| `5480104_5`、`5481702_5` | 同种子 `move_through_clutter` 性能采集，两项均为 `COMPLETED`，各完成 15 个评估并得到 5 条达成任务的轨迹。第一次缺少 GPU 样本，第二次得到 415 条，供 CPU/GPU 阶段分析使用。[性能对照](../reports/jobs_5480104_5481702_gpu_cpu_analysis.md) |
| `5481673`、`5481690` | GPU 诊断探针均为 `COMPLETED`，复现全局设备编号查询失败，并验证按作业内可见 GPU 的 UUID 采样。[首次探针](../logs/md-gpu-diagnostic-5481673.out) · [修正后的采样](../logs/md-gpu-diagnostic-5481690.gpu.jsonl) |

## Qwen 自动生成场景

| 作业 | 运行结果与用途 |
| --- | --- |
| `5485332` | `FAILED`。五次场景提案均未通过验证，记录用于追溯支撑和碰撞错误。[结果](../results/qwen_generated/qwen_261123_220933_ev3_jqvx/result.json) |
| `5485340` | `CANCELLED`。第 2 次提案完成注册，MotionDisco 搜索中途取消，保留当时的进度。[流程日志](../results/md-qwen-generate-5485340.out) · [取消日志](../results/md-qwen-generate-5485340.err) |
| `5485415` | `FAILED`。五次场景提案均未通过验证，记录用于追溯箱体越界和重叠。[结果](../results/qwen_generated/qwen_261123_225237_y5hiez19/result.json) |
| `5485423` | Slurm 为 `FAILED`，MotionDisco 启动器退出码为 0，流程结果为 `no_valid_trajectory`。保留为旧版目标配置的调试记录。[结果](../results/qwen_generated/qwen_261123_231149_tzxiv1vy/result.json) |
| `5485477` | `COMPLETED`。单独复评 `5485423` 的第 0 代，在更新目标容差后得到 1 条有效轨迹，终点误差约 0.87 cm。用于确认该候选的求解表现。[复评日志](../results/md-reach-retest-5485477.out) |
| `5489458` | `COMPLETED`。第 2 次提案完成注册，搜索完成 10 代评估。第 1、5、8 代由 MotionDisco 标记为 `to_valid`，均保存了轨迹。执行时使用了当时的二次验收流程。 [作业核验](../reports/job_5489458_verification.md) · [原始结果](../results/qwen_generated/qwen_261124_141926_7o3bcm5w/result.json) |
| `5490294` | `COMPLETED`。首轮提案完成注册，搜索完成 10 代评估。第 1、3、5、6、7 代由 MotionDisCo 标记为 `to_valid` 并保存轨迹。最高分为第 3 代（0.067000）。五条的 G1 终点误差均约 0.866 cm。 [作业核验](../reports/job_5490294_verification.md) · [原始结果](../results/qwen_generated/qwen_261124_183858_gp20xf7y/result.json) |

当前工作区的自动生成流程直接汇总 MotionDisco 的 `to_valid`。在 Karolina 登录节点的仓库根目录执行以下命令，可用 `5489458` 的提交参数重跑。

```bash
MOTIONDISCO_SEED=20261123 sbatch --parsable \
  scripts/16_qwen_generate_scene.sbatch --solve --nodes 10 --attempts 3
```
