# 七题 NR 下行复验

保留第一阶段 [设计题规范](../../tasks/design/tasks.json) 和[变更题规范](../../tasks/regression/tasks.json)的站点、时段、资源上限、业务流、QoS 门限和验收窗口。D01–D04 的最后一段是单向 ns-3.31 UDP 服务链路，C01–C03 重放 Hypatia 的马尼拉→大连原生路由，逐时更新最后一跳的服务容量。不同的协议在相同场景下可能产生不同判定，原阶段的数据与程序单独保留。

## 跨层接口

Skyfield 用合成轨道生成可见性、仰角和斜距。OpenSatCom 的原生预算结合口径增益、固定指向误差和自由空间损耗计算 C/N₀。传播层按当前频率和仰角再扣一次 ITU-R P.676-12 Annex 2 晴空气体衰减。下行假设完成同步及多普勒补偿，无 HARQ 重传。噪声和终端条件沿用原始任务。

物理层读取本阶段 OAI 单层 PDSCH 实测表，资源上限对应可容纳的最大实测 PRB 分配，实际占用频宽为 12 × PRB 数 × 子载波间隔。接收 SNR 由 C/N₀ 减去实际占用带宽的分贝值计算。只在同一 PRB、MCS、SCS、时隙长度和 TB 大小的已测 SNR 区间线性插值 BLER。每档业务速率由实测 TBS × (1−BLER) / 时隙长度得到，取可用候选 MCS 中速率最高的一档。继承第一阶段专用单向服务链路假设，按 1000 个完整下行时隙/s、每时隙一个传输块折算容量。OAI 的默认 TDD 日历每 10 ms 有 7 个完整下行时隙；采用这个日历时应另以 700 个完整时隙/s 评估业务门限。应用层只在该容量下做 IP/UDP 逐包回放。

D02、D04 的可编辑编码目录由第一阶段的 DVB-S2 档位改为 NR MCS 列表。原低速初始配置映射为单个低阶 MCS，其他无线侧配置沿用原值。新参考解须重新评分。D01、D03 和 C01–C03 沿用原任务的可编辑字段；C02 另在同一传播路径上交叉核对 22 cm 与 11 cm 接收口径的理论及实测 C/N₀ 差。

## 重放

从仓库根目录运行。先准备第一阶段 ns-3 镜像、第二阶段 ITU 镜像，以及 phase2/oai/curves.csv 实测表。主机仅需 Python 标准库和 Docker CLI。目标与回归各自写入指定目录，包含逐时刻 radio.jsonl、应用指标及断言。每条有效无线记录包含两端原始错误数和试验数、插值 BLER、实际 PRB 数、MCS 和 TBS。地平线或仰角门限以下记录为零容量。

```sh
python3 phase2/cases/replay.py D02 --profile target --output /tmp/chistar-nr-d02-initial
python3 phase2/cases/replay.py D02 --candidate candidate.json --profile regression --output /tmp/chistar-nr-d02-regression
python3 phase2/cases/replay.py C02 --profile old --output /tmp/chistar-nr-c02-old
python3 phase2/cases/replay.py C02 --candidate candidate.json --profile new --output /tmp/chistar-nr-c02-new
```

同一设计题检查初始不达标、参考达标、低负载回归和独立时段留出。每个需求变更题在主窗口和留出窗口分别执行“初始＋旧要求、初始＋新要求、参考＋旧要求、参考＋新要求”四组检查。运行失败会记录错误，缺测的 PRB/MCS/SNR 组合不会外推或用其他曲线补齐。受信评测器 verify.py 读取本地私有参考配置，并保留逐包原始证据。

## 本次结果与复核

- 第一轮固定四档 MCS（4、12、20、26），40 个预期中有多个未满足，只有 D04 完整通过。归档的实测表与结果位于 [four-mcs.csv](evidence/four-mcs.csv) 和 [first-four-mcs.json](evidence/first-four-mcs.json)。
- 最终共用八档目录 4、8、12、14、16、18、20、26 并加密 BLER 瀑布区后，七题的 40 个预期全部满足。原业务门限、时段、发射功率与终端口径配置保持第一轮口径，D02/D04 初始配置仍只使用低档 MCS 4。[判定和逐项业务指标](evidence/nr-runs.json)
- 独立审计对每轮 3000 个无线样本逐条核对。2970 个有效样本均能从其原生 OAI 输入点重算 SNR、插值 BLER 与逐时服务容量，30 个未接入样本均输出零速率。所有阶段的无线轨迹及所列公开输入均核对 SHA-256。[最终审计](evidence/audit.json)
- C02 在保持同一实际链路、只按每 10 ms 七个完整下行时隙折算平均容量时，8 秒业务窗口收包 854/1000，有效吞吐 1.257088 Mbps、p95 为 1019.97 ms。此次附加试验未满足新要求。这里只测量平均带宽下调的影响，未生成逐槽 TDD 调度与突发队列。[单独的敏感性结果](evidence/c02-700.json)

受信环境保有 private/specs.py 和阶段一私有留出窗口时，从仓库根目录可以重跑完整矩阵。验收器会在本次输出目录保存只读的曲线快照和输入指纹，完成时再次核对。

```sh
python3 phase2/cases/verify.py --output phase2/cases/private/final
python3 phase2/cases/summarize.py phase2/cases/private/final
python3 phase2/cases/audit.py phase2/cases/private/final
python3 phase2/cases/sensitivity.py phase2/cases/private/final
```
