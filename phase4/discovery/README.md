# 上游历史工程筛选

从 SNS3 官方主线提取 1,957 条提交标题，按功能分支和工程主题聚类。对入选的 9 个合并节点，逐一比较第一父提交和合并后提交的完整 Git 树，保存实际变动路径。另在 SNS3、StarryNet、gr-satellites、SatDump 的 7 个已合并 PR 核对合并时间、父提交及文件清单。[SNS3 分支与测试](sns3-changes.json) · [PR 与版本](changes.json)

以下条目是待做历史版本对照的候选，PR 使用平台的 changed_files 计数；树比较按路径计数，重命名可产生两个路径差异。文件数用于定位改动范围。工程复杂度要看可观察的行为依赖、验收强度与盲测表现。

| 实际变更 | 必须协同的工程部件 | 可执行验收或材料缺口 |
|---|---|---|
| SNS3 LoRaWAN 星上再生 | 星上/地面网关位置、终端 MAC、拓扑、帧转发、下行 ACK 时序 | 历史分支包含 regenerative 测试。需分别检查窗口内 ACK 命中和窗口外行为，以及移动终端重接入。 |
| SNS3 网关跨星切换 | 波束选择、网关和终端 MAC、PHY 重连、拓扑及统计归属 | 上游 handover 与 constellation 系统测试，可沿旧、新网关核对逐流业务。 |
| SNS3 多星再生与 ISL | 多星拓扑、星载转发、ISL、寻址、广播与地站业务 | 原生 constellation 和 regeneration 测试，检查跨星送达及保留单星回归。 |
| SNS3 动态频率计划 | 频率与波形配置、超帧分配、PHY 接收载波、载波统计 | 原生 dynamic-frequency-plan 示例，另有 frame-allocator 和 waveform-conf 测试。 |
| SNS3 DVB-S2X | 前向 BBFrame、波形/Bler 表、波束调度、终端和网关 PHY | 原生 waveform-conf 测试；需补业务级回归证明传播到上层。 |
| SNS3 波束跳变 PR #6 | 波束照射计划、网关调度、卫星发射状态、终端接收与业务队列 | 官方有照射表、原生示例和参考修改。需核对每波束服务窗口及端到端交付。 |
| SNS3 前向时分调度、返向按请求分配、MARSALA | 分别涉及 BBFrame 与 MAC/PHY 选通、容量请求到超帧授权、碰撞后相关与解码统计 | 三条独立历史记录；仍需为每条锁定负载和预期业务指标。 |
| StarryNet 任意拓扑 PR #29 | 拓扑输入、时变观测、编排器、链路同步、网络实例 | 已定位 11 个修改文件。需要原生环境对非规则拓扑检查邻接、可达路径及路由收敛。 |
| gr-satellites Mobitex-NX PR #723 | 符号同步、去交织、解扰、FEC、帧重组与卫星协议配置 | 有软符号向量、期望帧和多组 QA。适合做完整接收机子系统；工程范围到解帧。 |

### 已降级的材料

SNS3 的 `4abf38a5d` 分支标题含残余干扰，但相对第一父提交仅修改一份文档，故不能作为实现任务。StarryNet #31 有较大规模的编排实现改动，仍需明确与 #29 独立的需求和可判定结果。gr-satellites #755 的 C++/Python 绑定和 SatDump 的两条接收产品 PR 有真实补丁，当前材料缺少有代表性的网络业务验收。均保留为来源线索。

### 补充的从规格设计入口

- 华盛顿大学 ns-3-NTN 给出再生载荷与透明转发、真实几何传播时延、HARQ 和上层交付的建模依据。可据其公开工程评估网关馈电段是否正确接入跨层时间线，需另冻结可执行输入和参考输出。[实验室工程与文档](https://wp.ece.uw.edu/funlab/ns-3-ntn/)
- ESA 的 BEHOP 记录了真实系统中业务、波束地址和跳变信令的同步要求，可用于审查 SNS3 的建模边界。实际硬件验证需要项目设备。[ESA 项目](https://resilience.esa.int/archives/projects/behop)
- 5G-LENA 的 gsoc-leo-demo-example 包含轨道、3GPP NTN 信道和 NR 协议栈，可作为链路级交叉核对入口。仍需挑选足够复杂的明确变更与回归判据。[上游示例索引](https://cttc-lena.gitlab.io/nr/html/group__examples.html)

### 其他已定位输入的工程

- **ssloxford/qpep**。跨卫星代理比较 QUIC 与原生 TCP 的实际业务性能。核对相同业务、相同卫星工况下应用吞吐与完成时间，并区分代理、卫星链路、终端协议栈带来的差异。当前为候选。[opensand-testbed/benchmarks.py](https://github.com/ssloxford/qpep/blob/f134cb7ebd2a3f9e64dd677daa0acf51aaf16f9f/opensand-testbed/benchmarks.py) · [opensand-testbed/configurator.py](https://github.com/ssloxford/qpep/blob/f134cb7ebd2a3f9e64dd677daa0acf51aaf16f9f/opensand-testbed/configurator.py) · [opensand-testbed/docker-compose.yml](https://github.com/ssloxford/qpep/blob/f134cb7ebd2a3f9e64dd677daa0acf51aaf16f9f/opensand-testbed/docker-compose.yml)
- **CNES/dambox**。波束开关周期对网络服务与排队的影响。原作者提供 OpenSAND 测试和三组照射对照，可用端到端时延、抖动与吞吐验证波束时间线与应用业务是否匹配。当前为候选。[README.md](https://github.com/CNES/dambox/blob/c78a5d18fe82e2552d878c94a5dfaecdf5e29b4c/README.md)
- **serenade-project/SERENADE**。实时星座切换时更新数据平面和每个用户的 IP 路径。有原论文实验目录、业务发生器和源代码。先确定动态接入/路由事件，再用真实流的吞吐和延迟核验。当前为候选。[paper/README.md](https://github.com/serenade-project/SERENADE/blob/8eb04c6f11c11b66960aac7617a369e12f7e1215/paper/README.md) · [client/run_iperf_client.sh](https://github.com/serenade-project/SERENADE/blob/8eb04c6f11c11b66960aac7617a369e12f7e1215/client/run_iperf_client.sh) · [server/launch_iperf_servers.sh](https://github.com/serenade-project/SERENADE/blob/8eb04c6f11c11b66960aac7617a369e12f7e1215/server/launch_iperf_servers.sh)
- **igorauad/gr-dvbs2rx**。从 IQ 合成、同步、LDPC/BCH 到业务流的 DVB-S2 接收机。FEC 正确性与性能测试都有原生入口。还需补全从有噪 IQ、同步到业务负载的联合验收，才能作为完整接收机任务。当前为候选。[bench/fec/README.md](https://github.com/igorauad/gr-dvbs2rx/blob/130c31576cfeebb1a5842b24ccaf4a561b6a9990/bench/fec/README.md) · [bench/cpu/README.md](https://github.com/igorauad/gr-dvbs2rx/blob/130c31576cfeebb1a5842b24ccaf4a561b6a9990/bench/cpu/README.md) · [.github/workflows/test.yml](https://github.com/igorauad/gr-dvbs2rx/blob/130c31576cfeebb1a5842b24ccaf4a561b6a9990/.github/workflows/test.yml)
