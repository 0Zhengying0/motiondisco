# Karolina 作业 5490294 核验

`5490294` 于 2026 年 11 月 24 日 19:38:02–20:18:05（Europe/Prague）在 `acn12` 完成，Slurm 状态为 `COMPLETED`，退出码为 `0:0`。Qwen 首次提案即通过场景验证并注册。MotionDisCo 完成 **10/10 代评估**，保存 **5 条去重后的有效轨迹**。第 **3** 代的 Legacy 评分最高，为 **0.067000**。 [作业日志](../results/md-qwen-generate-5490294.out) · [流程结果](../results/qwen_generated/qwen_261124_183858_gp20xf7y/result.json) · [Slurm 账务](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/karolina_sacct.psv)

## 场景生成

注册场景为 `generated.qwen_261124_183858_gp20xf7y`。地面为 6 × 4 m，G1 从平面坐标 `(0.5, -1.0)` 走向 `(1.0, 1.0)`，直线距离为 2.062 m。短平台上放一个绿箱，白箱放在地面。MuJoCo 3.13.0 的 2 秒静置仿真中，两箱位置漂移均约 0.175 mm。场景生成请求耗时 80.18 s，其中 Ollama 记录模型加载耗时 65.77 s。验证与注册耗时 0.84 s。 [场景配置](../results/qwen_generated/qwen_261124_183858_gp20xf7y/scene_spec.json) · [MuJoCo 验证](../results/qwen_generated/qwen_261124_183858_gp20xf7y/validation.json) · [生成阶段计时](../results/qwen_generated/qwen_261124_183858_gp20xf7y/scene_generation_performance.jsonl)

## MotionDisCo 轨迹结果

第 0 代使用默认 `initial.py`，只产生一个接触模式。第 4、8、9 代因接触计划重复跳过求解。其余 6 个候选通过 KSO 并获得 TO 输出，其中 5 个收敛且达到 TO 硬终端目标。第 2 代未收敛，终端目标未达成，评估记录了关节位置超限、接触间隙和滑移。流程按 MotionDisCo 原生的 `to_valid` 汇总有效轨迹。 [Hydra 配置](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/.hydra/config.yaml) · [逐代 CSV](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/motiondisco_candidate_performance.csv) · [第 2 代诊断](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_2/results/extra.json)

| 代 | 接触模式 | 保存状态数 | Legacy 分数 | G1 基座终点误差 | 轨迹 |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 9 | 181 | 0.054614 | 0.8659 cm | [to_run.pkl](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_1/results/to_run.pkl) |
| **3** | 8 | 161 | **0.067000** | 0.8660 cm | [to_run.pkl](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_3/results/to_run.pkl) |
| 5 | 8 | 161 | 0.050253 | 0.8658 cm | [to_run.pkl](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_5/results/to_run.pkl) |
| 6 | 8 | 161 | 0.054090 | 0.8659 cm | [to_run.pkl](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_6/results/to_run.pkl) |
| 7 | 9 | 181 | 0.062643 | 0.8659 cm | [to_run.pkl](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_7/results/to_run.pkl) |

终点误差取保存状态的末帧 G1 基座到目标 XYZ 的三维距离。五条轨迹的实际终点均约为 `(0.995, 0.995, 0.770) m`，两箱的保存状态始末位置均相同。第 3 代的评估反馈还标记了两个无接触变化的过渡。 [终点误差明细](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/motiondisco_candidate_performance.csv) · [第 3 代指标](../results/qwen_generated/qwen_261124_183858_gp20xf7y/motiondisco/gen_3/results/metrics.json)

## 耗时与复现参数

| 项目 | 记录 |
| --- | --- |
| 墙钟和主机资源 | 40 分 03 秒。分配 16 个 CPU，累计使用 7,600 CPU 秒，墙钟平均使用 3.16 核。批作业峰值 RSS 为 29.88 GiB。[Slurm 账务](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/karolina_sacct.psv) |
| GPU | 1 张 A100-SXM4-40GB，折合 0.6675 GPU 分配小时。480 条设备样本的利用率均值为 4.16%，观测峰值为 100%。显存占用均值为 4,198 MiB，观测峰值为 15,109 MiB。[GPU 采样](../results/md-qwen-generate-5490294.gpu.jsonl) |
| 搜索与求解 | 搜索墙钟 2,208.51 s。提案累计 389.26 s，候选评估累计 1,469.21 s，其中 KSO 180.99 s、TO 1,277.32 s。TO 内的构建累计 775.27 s。 [逐运行 CSV](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/motiondisco_runs.csv) |
| Ollama | 场景生成 1 次，搜索聊天 18 次（325.56 s），embedding 11 次（64.00 s）。三类请求均无 HTTP 错误。 [服务日志](../results/md-qwen-generate-server-5490294.log) · [逐运行 CSV](../results/qwen_generated/qwen_261124_183858_gp20xf7y/audit/motiondisco_runs.csv) |
| 提交参数 | `--solve --nodes 10`，场景生成尝试上限采用默认值 5，场景和搜索种子均为 `20261123`。MotionDisCo 基线提交为 `c37491362a0678b60a594a7aabb007f0fed98420`，运行时带工作区改动。FARO 为 `458afa0cef22b498a68aaccb232e08942880f333`。 [源码指纹](../results/qwen_generated/qwen_261124_183858_gp20xf7y/scene_generation_performance.jsonl) · [模型 digest](../results/md-qwen-generate-5490294.performance.jsonl) |
