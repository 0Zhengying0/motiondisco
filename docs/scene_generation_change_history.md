# SceneSpec 场景生成：改动历史与恢复指引

记录日期：2026-11-24。目的：为初步验证自动场景生成模块，尽可能保持 MotionDisCo 原有搜索、初始程序、评分、KSO/TO 和有效性判定不变；将已经撤销及仍然保留的适配集中归档，以便后续有明确需求时选择性恢复。此文档不改变任何运行代码。

## 版本锚点

- [452985b：场景生成前的复现基线](https://github.com/0Zhengying0/motiondisco/commit/452985bd001e61e1e243ddfcbdbcd71767892be5)
- [d9852d3：SceneSpec v1](https://github.com/0Zhengying0/motiondisco/commit/d9852d375120f00448db559e1417483ecab13611)
- [c374913：SceneSpec v1.1](https://github.com/0Zhengying0/motiondisco/commit/c37491362a0678b60a594a7aabb007f0fed98420)
- [8335410：SceneSpec v1.2](https://github.com/0Zhengying0/motiondisco/commit/8335410fa0c7a31f0ebc9e58268c34ea24021010)

## 四处已有文件的适配

| 文件 | 改动 | v1.2 状态 |
| --- | --- | --- |
| examples/loco_manipulation/_task_loader.py | 对声明式生成场景增加 PRESERVE_SCENE_PHYSICS 分支 | 保留；对求解条件有影响 |
| examples/loco_manipulation/register_generated.py | 新增 --scene-spec JSON 验证注册入口，原 --examples 入口保留 | 保留；接口扩展 |
| shinka/launch_hydra.py | 将 _revision() 提取为公共 source_revision()，调用逻辑不变 | 保留；实验记录重构 |
| shinka/performance.py | 提供 source_revision()，记录 commit、dirty、源码变更 SHA-256 | 保留；实验记录重构 |

### _task_loader.py：需特别保留历史的三个操作

复现基线加载逻辑：
```python
scene_obj = with_collision_margin(with_sliding(registry.make_scene(s)), COLLISION_MARGIN)
# ... resolve initial state and goals ...
t_goal = with_to_goal(t_goal, TO_GOAL, TO_GOAL_TOL)
```

v1 增加生成场景模块的 PRESERVE_SCENE_PHYSICS = True 标记。对于带此标记的场景，跳过 with_sliding（额外滑动接触权限）、with_collision_margin（全局碰撞余量）和 with_to_goal（全局 TO 目标模式/容差覆写），保留场景定义的接触权限、碰撞设置和目标参数。禁止额外 layout 覆写已通过验证的初态。对不带标记的原始场景执行原有三个操作。

原因：避免验证阶段与求解阶段场景参数不一致，以及全局目标覆写新任务的精度要求。注意：这不是完全透明的接口适配，可能改变新场景的可行接触、碰撞约束、目标容差与最终求解结果；滑动权限变化并不必然破坏静态场景稳定性。目前没有对照实验隔离三项改动的影响。v1.2 仍保留此分支，不能声称新旧场景加载条件完全相同。

若以后需要恢复原加载机制：参考基线 452985b 中该文件的 load_task()，选择性恢复三个操作，并核对全局 TO_GOAL/TO_GOAL_TOL 对 reach_position 任务目标容差的影响；不要直接覆盖其他功能或历史产物。若以后要重新启用本适配，可从 d9852d3/c374913 的同文件选择性取回 preserve_physics 分支及生成场景标记。应验证原九场景不受影响，并用同一场景和种子做 A/B 实验。这里仅记录，不实施撤销。

## 已撤销的方案与独立验收

| 项目 | v1 | v1.1 | v1.2 |
| --- | --- | --- | --- |
| 初始程序 | walking_seed.py：ceil(distance/0.30) 预设步数 | 恢复 initial.py，删除 walking_seed.py | 保持原始初始程序 |
| 评分 | quality | 恢复 legacy | legacy |
| evaluate.py | 将独立终点验收及额外物理检查并入 to_valid | 恢复基线 evaluate.py；独立验收移到 acceptance.py | 保持原评估器 |
| 独立验收 | 评估器内 | acceptance.py 读取已保存且 to_valid 的去重轨迹，物理复核 + 三维终点误差 ≤ 0.10 m | 删除 acceptance.py；直接汇总原生 to_valid 且存在 to_run.pkl 的去重轨迹 |
| reach_position 目标 | 旧运行逐轴 TO 0.10 m | KSO 0.10 m/轴、TO 0.005 m/轴，独立距离阈值 0.10 m | 保留任务目录中的容差；终点误差由离线统计计算，不作为工作流额外筛选 |

恢复参考：
- [旧 walking_seed.py](https://github.com/0Zhengying0/motiondisco/blob/d9852d375120f00448db559e1417483ecab13611/examples/loco_manipulation/scene_generation/walking_seed.py)：仅作为将来 warm-start 对照实验候选，不能混入原始基线。
- [v1.1 acceptance.py](https://github.com/0Zhengying0/motiondisco/blob/c37491362a0678b60a594a7aabb007f0fed98420/examples/loco_manipulation/scene_generation/acceptance.py)：若大规模训练数据需要独立任务验收，可只恢复 completion_check，保持物理复核可选；不要重新定义原评估器的 to_valid。
- 原生 ToSolve.valid = (converged or physically_valid) and goal_met。收敛轨迹未必运行额外 trajectory_check。删除额外验收不是删除原生约束与检查。
- 场景生成前的格式、支撑拓扑、几何及 MuJoCo 两秒静置验证始终保留。场景新颖性与接触程序新颖性是不同检查。

## 实验追溯

- 5485332、5485415：各五次场景生成失败。
- 5485340：第二次生成通过验证，搜索中断。
- 5485423：第五次生成通过；旧目标容差下六条收敛且物理复核通过，但独立误差均超过 10 cm。
- 5485477：单独复评 5485423 第 0 代，调整目标容差后终点误差约 0.87 cm；不是新场景完整搜索。
- [5489458](../reports/job_5489458_verification.md)：v1.1，第二次生成通过，10/10 评估，三条独立验收通过。
- [5490294](../reports/job_5490294_verification.md)：v1.2，首次生成通过，10/10 评估，五条原生 to_valid 去重轨迹；报告离线终点误差约 0.866 cm。运行时源码基线 c374913，带工作区改动。两次新实验的场景和验收口径不同，不宜将 3→5 归因于删除验收或任何单一修改。

本记录依据上述提交代码和仓库核验报告；不替代原始运行产物，不重跑实验。原始历史保留不覆盖。
