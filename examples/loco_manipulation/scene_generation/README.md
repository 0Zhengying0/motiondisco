# Qwen 场景生成与 MotionDisCo 求解

```text
Prompt + 资产目录 + 任务目录 + JSON Schema
  → Qwen 生成 SceneSpec
  → Python 转换为 FARO 场景、初态和目标
  → MuJoCo 验证 ──失败──→ 结构化反馈交给 Qwen 修订
  → 注册为 generated.<scene_id>
  → MotionDisCo 搜索接触计划 → KSO → TO → 物理与终态验收
  → result.json、逐代记录和 to_run.pkl
```

## 1. 在 Karolina 提交完整流程

从仓库根目录执行下面一组命令。 [Slurm 提交脚本](../../../scripts/16_qwen_generate_scene.sbatch)

```bash
cd /mnt/proj1/eu-26-37/it4i-dianyu/Zhengying/motiondisco
mkdir -p results
job_id=$(MOTIONDISCO_SEED=20261123 sbatch --parsable \
  scripts/16_qwen_generate_scene.sbatch --solve --nodes 10)
job_id=${job_id%%;*}
printf 'Job ID: %s\n' "$job_id"
```

`--solve` 把验证通过的场景接入 MotionDisCo。省略它时，作业在验证并注册后结束。`--nodes` 设置 MotionDisCo 的候选代预算。`--brief "设计要求"` 把额外说明附到场景生成 Prompt。`MOTIONDISCO_SEED` 设置生成和搜索共用的基础种子，`--seed` 单独覆盖场景生成种子。作业记录种子来源、逐次生成种子和搜索派生种子。

脚本在计算节点启动本地 Ollama，加载已有缓存模型，再在 Apptainer 中调用 `python -m examples.loco_manipulation.scene_generation generate`。Slurm 使用 `zy.xu@tum.de` 发送开始、结束、失败和墙钟时限提醒。查看队列和实时日志：

```bash
job_log="results/md-qwen-generate-${job_id}.out"
squeue -j "$job_id"
tail -F "$job_log"
```

按 Ctrl+C 退出日志跟随，Slurm 作业继续运行。stdout 中的 `Run artifacts:` 给出本次输出目录。下文用 `$run_dir` 表示这个目录。

## 2. Qwen 接收 Prompt 并生成 SceneSpec

[__main__.py](./__main__.py) 的 `generate()` 读取 [prompt.txt](prompt.txt)，把 [asset_catalog.json](asset_catalog.json)、[task_catalog.json](task_catalog.json) 和 [scene_spec.schema.json](scene_spec.schema.json) 的完整内容拼进同一个 `prompt` 字段。场景 ID、可选设计说明、[novelty.py](novelty.py) 提供的已有场景支撑拓扑，以及重试时的上一版回答和结构化错误也在这里。程序向本地 Ollama 的 `/api/generate` 请求 JSON，Qwen 根据正文中的候选资产和任务设计场景。

返回的 SceneSpec 顶层包含 `schema_version`、`scene_id`、`floor`、`robot`、`objects` 和 `task`。关键字段为 `floor.half_extents`、`robot.initial_xy_yaw`、各实例的 `asset_id`、`instance_id`、`support_object`、`support_surface`、`relative_xy_yaw`，以及 `task.type` 和 `task.parameters.target_xy`。

| 输入与输出 | 对应代码或文件 |
| --- | --- |
| 资产目录 | [catalogs.py](catalogs.py) 的 `build_asset_catalog()` 从 [原始资产提取 JSON](../../../results/motiondisco_object_catalog.json) 生成目录，复制尺寸、质量、RGBA 和接触权限，并记录来源指纹。 |
| 任务目录和 JSON Schema | [task_catalog.json](task_catalog.json) 定义任务参数、FARO 目标和达成检查。[spec.py](spec.py) 的 `SceneSpec` 与 `scene_schema()` 提供 Python 解析模型和 JSON Schema。 |
| 发给 Qwen 的实际内容 | `$run_dir/attempt_*/prompt.txt` 保存拼接后的完整正文，包括三个 JSON。 `request.json` 保存同一请求的正文、模型和生成参数。 |
| Qwen 的原始输出 | `$run_dir/attempt_*/response.txt` 保存原文，`scene_spec.json` 保存可解析的 JSON。同目录保存 `ollama_response.json`，请求失败时保存 `request_error.json`。 |
| 模型与输入快照 | `$run_dir/model.json` 保存 Ollama 版本及模型信息，运行目录还保存实际发送的资产目录、任务目录和 Schema。 |

更新原始提取数据或规格后，可从仓库根目录重新生成目录和 Schema：

```bash
../envs/motiondisco/bin/python -m examples.loco_manipulation.scene_generation.catalogs
../envs/motiondisco/bin/python -m examples.loco_manipulation.scene_generation.spec
```

## 3. Python 转换，MuJoCo 验证并注册

`generate()` 把每次回答交给 [register.py](register.py) 的 `register_spec()`。它先调用 [validate.py](validate.py) 的 `validate()`，再根据报告决定是否注册。具体调用顺序如下。

1. **解析 SceneSpec。** [spec.py](spec.py) 的 `parse_spec()` 和 `check_references()` 检查 JSON、字段、资产引用和支撑关系。[novelty.py](novelty.py) 的 `check_novelty()` 对照已有场景。
2. **转换成 FARO 定义。** [convert.py](convert.py) 的 `make_scene()` 用 `Scene`、`Plane`、`FixedBox`、`MovableBox` 和 FARO 原有 G1 模型构建场景。`initial_state()` 用 `StateSpec`、`OnFace` 和 `Standing` 放置物体与机器人。FARO 解析世界位姿、初始接触和表面 ID。`reach_discrete()` 和 `reach_terminal()` 提供求解所需的离散接触目标及 `TerminalGoal/PositionTarget`。
3. **验证场景。** [validate.py](validate.py) 用 FARO 的 `build_mujoco()` 编译同一场景。`check_geometry()` 检查地面、支撑面及箱体相交，`check_standing()` 检查 G1 起点和目标站姿，`check_stability()` 通过 MuJoCo 接触与静置仿真检查箱体稳定性。每次报告进 `$run_dir/attempt_*/validation.json`。越界反馈包含箱体中心的允许范围，同一支撑面上的箱体重叠会给出可分离的摆放轴和区间。失败报告会随上一次 JSON 发给 Qwen 修订，最后一次修订可选更简单的摆法。通过后，运行根目录保存最终 `scene_spec.json` 和 `validation.json`。
4. **注册供 MotionDisCo 读取。** [register.py](register.py) 写入 `examples/loco_manipulation/scenes/generated/<scene_id>/`。其中 `scene.py`、`initial_conditions.py` 和 `goals.py` 接入 FARO 的场景、初态和目标注册表，`scene_spec.json` 和 `asset_catalog.json` 保存输入快照，`spec.json` 提供 campaign 用的描述和箱体清单。[_task_loader.py](../_task_loader.py) 的 `load_task()` 读取同一组物理参数、初态、接触权限和目标。

单独验证已有 SceneSpec，或手动注册一份新的 SceneSpec 时，从仓库根目录执行：

```bash
PY=../envs/motiondisco/bin/python
spec_path=/absolute/path/to/scene_spec.json  # 换成实际文件路径
"$PY" -m examples.loco_manipulation.scene_generation validate "$spec_path"
"$PY" examples/loco_manipulation/register_generated.py --scene-spec "$spec_path"
```

手动注册会重新验证。生成作业输出的已注册场景可直接用 `result.json` 里的 `scene`，例如 `generated.qwen_261123_221122_em27_fb2`。用 [scene_campaign.py](../scene_campaign.py) 的 dry-run 检查现有 campaign 能否发现它：

```bash
scene=generated.qwen_261123_221122_em27_fb2  # 换成实际注册名
"$PY" examples/loco_manipulation/scene_campaign.py --only "$scene" --valid 1 --dry-run
```

## 4. 交给 MotionDisCo 并读取结果

[__main__.py](./__main__.py) 的 `solve()` 把注册名和任务描述传给现有 `motiondisco_launch`，使用 `ollama_local`、MotionDisCo 默认 [initial.py](../initial.py) 和默认评分。后续沿原流程提案、检查接触计划、运行 KSO 和 TO。场景搜索日志在 `$run_dir/motiondisco/evolution_run.log`，候选记录在 `$run_dir/motiondisco/gen_*/results/`。

搜索结束后，[acceptance.py](acceptance.py) 读取 MotionDisCo 判定有效的保存轨迹，调用现有 [trajectory_check.py](../trajectory_check.py) 做物理检查，再通过 [convert.py](convert.py) 的 `reach_completion()` 检查末帧 G1 基座位置。独立结果写入 `acceptance.json`，通过的轨迹汇总进 `result.json`。

作业结束后，从 Slurm 日志找到输出目录，再打开汇总：

```bash
run_dir=$(sed -n 's/^Run artifacts: //p' "$job_log" | head -n 1)
if [[ -n "$run_dir" ]]; then
  cat "$run_dir/result.json"
else
  cat "results/md-qwen-generate-${job_id}.err"
fi
```

| 找什么 | 查看哪里 |
| --- | --- |
| 成功或失败在哪一步 | `$run_dir/result.json`。 `solved` 表示已有验收通过的轨迹，`registered` 表示此次流程停在注册，`validation_exhausted` 表示生成重试耗尽，`no_valid_trajectory` 表示搜索结束但没有合格轨迹，`solver_failed` 表示求解入口报错。作业中断时用 Slurm 状态和逐代记录确认最后进度。 |
| 通过的是哪一代 | `result.json` 的 `valid_plans[].gen` 指向 `motiondisco/gen_*/`。读取对应 `results/acceptance.json` 的 `pass`、`solver_to_valid`、`to_physical.pass`、`task_completion.met` 和 `task_completion.error_m`。 |
| 数值轨迹和候选详情 | 同目录的 `to_run.pkl` 保存数值轨迹，`metrics.json` 保存评分和阶段判定，`extra.json` 保存 MotionDisCo 自己的接触序列、阶段判定和失败诊断。 |

已有场景可用同一 Python 模块的 `solve` 子命令重跑。在已分配的 Karolina 计算节点上，从 MotionDisCo 仓库根目录执行。若该节点尚未启动 Ollama，在同一节点的另一个终端运行：

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$(realpath ../models/ollama)" \
  ../tools/ollama/bin/ollama serve
```

保持 Ollama 运行，在求解终端执行以下命令。 `$scene` 使用上一步的注册名。

```bash
root=$PWD
base=$(dirname "$root")
prefix="$base/envs/motiondisco"
acados="$root/submodules/faro/extern/acados"
curl -fsS http://127.0.0.1:11434/api/tags
solve_out=$(mktemp -d "$root/results/qwen_solve.XXXXXX")
apptainer exec --cleanenv --bind "$base:$base" --pwd "$root" \
  --env "PATH=$prefix/bin:/usr/local/bin:/usr/bin:/bin,PYTHONPATH=$root,PYTHONNOUSERSITE=1" \
  --env "ACADOS_SOURCE_DIR=$acados,LD_LIBRARY_PATH=$acados/lib:$prefix/lib" \
  --env "MOTIONDISCO_PERFORMANCE=1,SHINKA_PRICING_MODE=offline,SHINKA_IK_MAX_NUM_NODES=50,SHINKA_TO_N_JOB=1" \
  "$base/containers/miniforge3.sif" "$prefix/bin/python" \
  -m examples.loco_manipulation.scene_generation solve "$scene" --out "$solve_out" --nodes 10
cat "$solve_out/result.json"
```

## 5. 导出性能记录

下面的命令在作业结束后刷新 Slurm 账务，另存逐运行、逐场景和逐候选 CSV。若已有账务快照，可将 `--refresh-sacct` 换成 `--sacct "$snapshot"`。 [详细提取器](../../../reports/extract_motiondisco_performance.py)

```bash
audit_dir=$(mktemp -d)
../envs/motiondisco/bin/python reports/extract_motiondisco_performance.py \
  --job-id "$job_id" --refresh-sacct --output-dir "$audit_dir"
printf 'Audit files: %s\n' "$audit_dir"
```

| 记录内容 | 原始入口和位置 |
| --- | --- |
| 作业状态、退出码、CPU 时间、峰值 RSS、GPU 分配、设备样本 | Slurm `sacct` 与 [karolina_performance.py](../../../scripts/karolina_performance.py)。 `results/md-qwen-generate-<job_id>.performance.jsonl` 保存作业和模型事件，`...gpu.jsonl` 保存设备 UUID、利用率和显存，`results/md-qwen-generate-server-<job_id>.log` 保存 Ollama 设备、模型装载及 HTTP 请求。 |
| 场景生成、验证与搜索准备 | [__main__.py](./__main__.py)、[validate.py](validate.py) 和 [shinka/performance.py](../../../shinka/performance.py)。 `$run_dir/scene_generation_performance.jsonl` 保存请求、token、验证阶段计时、工作区状态和源码指纹。 |
| MotionDisCo 配置和逐代性能 | [shinka/launch_hydra.py](../../../shinka/launch_hydra.py)、[performance_context.py](../performance_context.py) 及现有求解器事件。 `$run_dir/motiondisco/` 下的 `.hydra/config.yaml`、`run_performance.jsonl`、`gen_*/proposal_performance.jsonl` 和 `gen_*/results/evaluation_performance.jsonl` 保存实际搜索配置、种子、提案、接触检查、KSO、TO 和验收计时。 |
| 三张 CSV 的核验口径 | [performance_records.py](../../../reports/performance_records.py) 和 [extract_motiondisco_performance.py](../../../reports/extract_motiondisco_performance.py) 分开汇总场景生成、搜索聊天和 embedding，区分工作流结局与搜索预算，统计候选、失败、中断、有效与去重轨迹、最佳评分和资源成本。提取器还会从保存的轨迹复算 G1 终点误差。口径对照见 [基础性能报告](../../../reports/motiondisco_performance_report.md) 和 [5481702 核验](../../../reports/job_5481702_verification.md)。 |

## 边界条件

**场景与输入。** 第一版 `schema_version=1`，仅开放 `reach_position` 和 `table_short`、`table_tall`、`green_box`、`white_box`、`yellow_box`、`crate`。场景含 0–2 个固定平台和 0–2 个可移动箱子，合计至少 1 个。实例可复用资产，ID 必须唯一。已注册的同名场景会返回 `SCENE_ID_EXISTS`。场景和实例 ID 以小写字母起始，后续只允许小写字母、数字和下划线，总长至多 48 字符，实例名避开 `floor`、`robot` 和机器人接触通道。地面以世界原点为中心，全长 3–8 m、全宽 2–5 m，`half_extents` 填半长和半宽。G1 起点和目标为世界 XY，水平距离 0.8–3 m。物体的 `relative_xy_yaw` 按支撑面局部坐标填，XY 单位为米，Schema 的 x、y 范围分别是 `[-4, 4]` 和 `[-2.5, 2.5]`，物理检查还要求落在实际地面和支撑内。yaw 单位为弧度且在 `[-π, π]`。支撑面为 `floor.surface` 或另一物体的 `top`，支撑链须汇到地面，固定平台须用固定支撑。系统提供一台 G1，站立高度和默认关节角取 FARO。规格只接收声明式 JSON，物理参数来自资产目录。与旧场景有相同资产及支撑拓扑的结果会被拒绝，坐标、朝向或重命名不会改变该判定。**场景验证。** FARO Plane 的碰撞面无限延伸，有限边界单独检查，地面与支撑投影容差为 1 µm。支撑间隙容差为 10 µm，箱体穿透深度超过 1 mm 失败。G1 双足使用 1 mm 接触接近量，允许 2 mm 足底地面穿透，机器人与箱体或平台发生碰撞时失败。目标站姿按起点 yaw 检查，求解终态 yaw 自由。静置仿真 2 s，G1 保持初始姿态并排除碰撞响应。箱体须保持声明支撑，位移和姿态漂移分别不超过 5 mm 和 0.03 rad，最后 0.25 s 的线速度和角速度分别不超过 0.01 m/s 和 0.05 rad/s。相切接触可用 10 µm 位移探测，仿真从恢复后的原位开始。阈值用 `box_stacking`、`move_through_clutter` 和 `long_dist_pick_place` 的已知初态在 MuJoCo 3.13.0 校准，箱中心最大漂移低于 0.176 mm，角度漂移低于 0.000001 rad，最后 0.25 s 的线、角速度分别低于 0.000000001 m/s 和 0.00000001 rad/s。场景验证阶段独立于 KSO 和 TO。**执行与验收。** 提交脚本默认申请 1 张 A100、8 个 CPU、32 GiB 内存和 1 小时 45 分钟，达到时限 80% 时发邮件。场景模型默认为 `qwen2.5-coder:14b`，默认至多 5 次场景生成，每次请求超时默认 600 秒。完整搜索按候选预算或终止状态返回。通过场景验证后仍需等待独立的轨迹结果。KSO 和 TO 的 FARO 位置界按 XYZ 分量施加，前者每轴 0.10 m，后者每轴 0.005 m。较紧的 TO 位置界为默认 0.05 的求解残差留出余量。计入结果的轨迹须有保存文件，TO 有效、物理复核通过，且实际末帧基座 XYZ 距目标的三维欧氏距离不超过 0.10 m。`--nodes` 增加的是候选预算，轨迹是否可解由运行结果确定。**账务与适用范围。** GPU 每 5 秒采样一次，统计量为设备样本均值和观测峰值，CPU 和 RSS 取作业账务，嵌套阶段计时有重叠。账务缺项留空，实测为零保留为零。真实设备及邮件结果以实际提交后的记录为准。独立渲染、安装和单独复评属于其他入口。
