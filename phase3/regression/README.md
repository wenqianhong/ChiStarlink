# 33 道需求变更与回归任务

C101–C133 是第二阶段 C01、C02、C03 的合成变体。每题有初始工程配置、旧需求、新需求和允许修改的参数。输入、判据与业务负载均在运行前确定；33 个候选经过主窗口及留出窗口的完整矩阵筛选。

| 编号 | 变更机制 | 验收重点 |
| --- | --- | --- |
| C101–103 | 忙时负载提升 | 增加供给后保留旧流量服务 |
| C104–106 | 分配带宽上限收紧 | 减少占用后继续满足业务 |
| C107–109 | 更小的接收口径 | 补偿接收增益变化 |
| C110–112 | 馈线损耗增大 | 在新的链路损耗下保持交付 |
| C113–115 | 终端指向误差增大 | 计入方向图衰减并保持时延 |
| C116–118 | 系统噪温上升 | 重算 C/N₀ 和 NR 调度有效速率 |
| C119–121 | 星上功率限额降低 | 满足新功率上限并保持服务 |
| C122–124 | 完整下行时隙份额减少 | 先折算当前服务份额，再运行网络 |
| C125–127 | 更窄的可解调 MCS 目录 | 只从接收端支持的实测组合选档 |
| C128–130 | P95 单向时延门限降低 | 从逐包时戳验证时延与原有吞吐 |
| C131–133 | 接收天线口径效率下降 | 用新效率重算增益并维持交付 |

## 复跑主场景

使用已构建的第二阶段 ITU/Skyfield/OpenSatCom 容器、OAI 标定表、第一阶段 Hypatia/ns-3 容器。镜像构建入口见[第二阶段说明](../../phase2/cases/README.md)与[原生网络说明](../../tasks/regression/README.md)。从仓库根目录执行。原生网络输入来自镜像内的 Hypatia 端到端测试工程；运行时容器使用离线模式。

```sh
python3 phase3/regression/replay.py C101 --condition old --output /tmp/c101-old
python3 phase3/regression/replay.py C101 --condition new --output /tmp/c101-before
python3 phase3/regression/replay.py C101 --condition new --candidate my-edit.json --output /tmp/c101-after
```

未指定 candidate 时运行初始配置；候选 JSON 只填写任务允许修改的字段。退出码 0 表示实际验收通过。第二条命令用于复现旧工程违反新要求，退出码为 1。每次输出逐时无线及容量数据、收发包时间戳与机器可读判定。

## 模型和计数

- 共享的原生场景为马尼拉到大连的 17 星 Kuiper-630 测试子网。每 100 ms 从动态转发路径选择末跳发射卫星。Skyfield 传播同组 TLE，射频预算采用 12 GHz 晴空、自由空间及 P.676-12 气体损耗。初始相位与物理参数均为合成数据。
- 物理层复用第二阶段实测单层 NR PDSCH/AWGN 表，在相同 PRB、MCS、SCS、TBS 上插值。默认每秒服务预算为 1000 个完整下行时隙。C122–124 按新份额折算平均容量，未模拟真实逐时隙 TDD 日历。
- 指定方向每 100 ms 只保留一条有效网卡带宽赋值，运行前将其读回并与物理层速率及调度份额逐样本核对。Hypatia 的其余链路沿用原生配置，最终吞吐与 P95 来自逐包回放。
- 每题主场景、独立留出各有四组验收。依次为初始配置＋旧要求通过、初始＋新要求失败、参考＋旧要求通过、参考＋新要求通过。留出改变业务起点、持续时间和噪温偏移。保留 0.5 秒排空时间，吞吐分母为业务活动时间。
- [题目表](catalog.json)提供中文题干、逐模块约束和实测摘要。[工程与验收输入](tasks.json)列出可编辑项与数值。[逐次证据](evidence.json)保留判定、收发包数、净吞吐、P95 时延及无线/网络原始记录指纹。

受信评测端提供参考配置与留出输入后可运行全部 264 项。公开仓库保留用户自选候选方案的评分入口。

```sh
python3 phase3/regression/verify.py --controls phase3/regression/private/controls.json --output phase3/regression/private/final --jobs 2
python3 phase3/regression/publish.py --runs phase3/regression/private/final
```
