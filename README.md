# ChiStarlink

面向低轨卫星通信的可执行工程任务集。第一阶段在开源仿真链上验证 10 个派生任务，覆盖链路设计 4 题、跨层故障修复 3 题、需求变更回归 3 题。

[中文规划](index.html) · [第一阶段 HTML 报告](reports/phase-1.html)。下载仓库后可在浏览器中打开 HTML。逐题的输入、环境和实测记录如下。

| 任务 | 类别 | 公开证据 |
| --- | --- | --- |
| D01–D04 | [链路设计](tasks/design/README.md) | [16 次重放](tasks/design/evidence/design-results.json) |
| R01–R03 | [合成故障修复](tasks/repair/README.md) | [18 次重放](tasks/repair/evidence/results.json) |
| C01–C03 | [合成需求变更](tasks/regression/README.md) | [24 次重放](tasks/regression/evidence/summary.json) |

首批使用 Skyfield、OpenSatCom 的 DVB-S2 物理层抽象及 ns-3.31。设计与修复任务采用合成 Starlink 轨道输入和单向星地业务流，回归任务采用 Hypatia 的 17 星 Kuiper-630 测试子网。参考解与留出输入由评测端保管。MATLAB 原生重放另有[容器构建说明](containers/matlab-ntn/README.md)，需要相应许可。
