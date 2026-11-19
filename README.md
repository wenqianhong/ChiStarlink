# ChiStarlink

[浏览第三阶段 100 道派生题](reports/phase-3.html)。基于第二阶段 10 道母题新增链路设计 34 道、故障修复 33 道、需求变更 33 道。每题列出题干、可编辑输入、各层约束与逐次实测。公开重放入口见[设计](phase3/design/README.md)、[修复](phase3/repair/README.md)和[变更](phase3/regression/README.md)。

面向低轨卫星通信的可执行工程任务集。第一阶段在开源仿真链上验证 10 个派生任务，覆盖链路设计 4 题、跨层故障修复 3 题、需求变更回归 3 题。

第二阶段在同一批任务上改用 ITU 晴空气体衰减与 OAI 原生 NR PDSCH 标定。最终 58 次验收均符合预期。C02 在每秒 700 个下行时隙的额外实验中未满足吞吐与时延目标。[第二阶段 HTML 报告](reports/phase-2.html) · [OAI 标定与复验](phase2/oai/README.md) · [设计及变更结果](phase2/cases/evidence/nr-runs.json) · [修复结果](phase2/repair/evidence/summary.json)

[中文规划](index.html) · [第一阶段 HTML 报告](reports/phase-1.html)。下载仓库后可在浏览器中打开 HTML。逐题的输入、环境和实测记录如下。

| 任务 | 类别 | 公开证据 |
| --- | --- | --- |
| D01–D04 | [链路设计](tasks/design/README.md) | [16 次重放](tasks/design/evidence/design-results.json) |
| R01–R03 | [合成故障修复](tasks/repair/README.md) | [18 次重放](tasks/repair/evidence/results.json) |
| C01–C03 | [合成需求变更](tasks/regression/README.md) | [24 次重放](tasks/regression/evidence/summary.json) |

首批使用 Skyfield、OpenSatCom 的 DVB-S2 物理层抽象及 ns-3.31。设计与修复任务采用合成 Starlink 轨道输入和单向星地业务流，回归任务采用 Hypatia 的 17 星 Kuiper-630 测试子网。参考解与留出输入由评测端保管。MATLAB 原生重放另有[容器构建说明](containers/matlab-ntn/README.md)，需要相应许可。
