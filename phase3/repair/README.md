# 第三阶段 · 33 道跨层故障修复题

R101–R133 是从已通过第二阶段的 R01、R02、R03 派生的合成工程故障。R01 派生 5 道接入与几何题，R02 派生 14 道射频与传播题，R03 派生 14 道物理层和网络接口题。原始来源是 Hypatia 的合成 Starlink TLE、OpenSatCom 射频模型、ITU-Rpy P.676-12 晴空传播和 OAI NR 实测曲线。设备描述、变更情境和业务合同由本项目设定。[每题题干及逐层约束](catalog.json) · [198 次验收结果](evidence/results.json)

## 如何作答

每题的 `input/Rxxx/source.py` 定义新设备发布的数据格式，`input/Rxxx/adapter.py` 是可修改的故障工程。旧设备传入 `legacy` 字段。主场景和原有正常场景记录在 [scenes.json](scenes.json)，每题的编辑字段、负载及门限在 [specs.json](specs.json)。只需提交修改后的解码器。评测重新生成对应物理场景与消息，并运行完整的预算、波形表查询及分组模拟。

从仓库根目录运行。以下命令使用第二阶段的校准表和两个同版本 Docker 镜像；首次构建镜像可沿用 [ITU 模型构建步骤](../../phase2/propagation/README.md) 与 [Hypatia/ns-3 构建步骤](../../tasks/regression/README.md)。

```sh
python3 phase3/repair/replay.py R131 --case target --output /tmp/repair-R131
python3 phase3/repair/replay.py R131 --case regression --output /tmp/repair-R131
python3 phase3/repair/replay.py R131 --case target --adapter /path/to/your/adapter.py --output /tmp/repair-submission
```

若业务或接口不达标，单题命令返回 1。输出在指定目录的 `R131/submitted/target/` 或 `R131/submitted/regression/`，含逐时的 `layers.csv`、ns-3 输入 `trace.csv`、应用计数 `metrics.json` 和逐项断言 `judgment.json`。[33 个公开初始目标的无线层诊断记录](evidence/initial-target-traces.jsonl.gz)

## 实际仿真与验收

- **轨道与接入**。Skyfield/SGP4 根据冻结的合成 TLE 和地面站生成 12 秒站心几何，正常采样间隔为 1 秒。保护时隙任务额外保留 5 ms 边界。
- **射频与传播**。OpenSatCom 原生预算使用当轮距离、频率、收发参数和极化；晴空气体吸收按真实仰角计算并进入 C/N₀。气体衰减接口本身受损的题目同时记录其经过故障解码后的值。
- **NR 物理层**。以传播后的分配内信噪比查第二阶段冻结的 OAI 表，表指纹为 `3a8cc5db5719600f81c8b1c861461888e639615f851a7e5195b4ac2813d22452`。记录实测区间两端 SNR、错误数、试验数、MCS、PRB、TBS 和有效速率。场景采用独占单用户下行，基础时隙长度为 1 ms。资源份额题使用合同规定的可调度份额。
- **网络与业务**。原生 ns-3.31 按时间更新设备服务速率与单程传播/处理延迟，生成独立 IPv4/UDP 应用收包计数和时戳。验收要求交付率及有效负载吞吐都达到 offered load 对应值的 98%，p95 满足各题上限。故障候选必须在业务层也表现出可观测退化。R131 的触发特别体现在 p95：故障版收全 1500 包但为 6.139 ms，修复后收全且降至 3.939 ms，合同要求 ≤5.5 ms。
- **来源边界**。本批覆盖移动单向服务链路、AWGN 实测曲线、短窗口 UDP 流。未将这些派生问题认作原始设备现网缺陷，也未将采样容量抽象计作每包运行的 NR 波形。

## 筛选记录

初次的 33 个候选共 198 次重放，197 格符合预期。原 R111「馈线插损被重复计入」在留出场景的故障版本中，接口断言异常但全部业务指标仍通过。该候选被拒收，换为不同的「射频继电器误用隔离端口损耗」候选，保留同一业务合同和相同留出输入。重新执行了最终全体 198 次重放。[拒收说明和判定指纹](evidence/rejected.json)

最终每题覆盖**初始/参考 × 触发/旧格式回归/留出**六格，合计 **198/198 符合预期**。其中 66 个故障目标或故障留出运行的业务未达标；两版旧格式和参考目标、参考留出共 132 个运行通过。每次运行均记录指标和判断，不只比较补丁文本。

在保留私有评测输入的工作区，以下命令可以完整复验并重新汇出公开证据：

```sh
python3 phase3/repair/verify.py --private phase3/repair/.private --output phase3/repair/.private/full --workers 2
python3 phase3/repair/publish.py --full phase3/repair/.private/full
```

私有目录含 `reference/R101.py` 至 `reference/R133.py` 与 `holdout.json`，以及筛选和运行产生的逐层日志。公开矩阵保留结果与判定文件指纹。
