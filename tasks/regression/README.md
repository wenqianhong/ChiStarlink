# 需求变更后的全链路回归

C01、C02、C03 来自同一个可原生运行的 Hypatia 端到端测试工程。三道题分别改变业务负载、终端口径和星上功率上限。它们属于合成变更。需求、可修改字段、旧配置以及新旧门限见 [tasks.json](tasks.json)。

## 原生工程和模型

- 拓扑选自 [Hypatia 原生端到端测试的数据目录](https://github.com/snkas/hypatia/tree/0ac531c313eba2335f6344b46347140c3a0d4230/ns3-sat-sim/simulator/test_data/end_to_end)。该测试保留 17 颗标为 Kuiper-630 的卫星、马尼拉和大连两个站点、TLE、星间链路和每 100 ms 的动态转发表。节点 17 经星间路径向节点 18 发送 UDP。输入沿用上游作者提供的测试子网。
- 先使用 [main_satnet](https://github.com/snkas/hypatia/blob/0ac531c313eba2335f6344b46347140c3a0d4230/ns3-sat-sim/simulator/scratch/main_satnet/main_satnet.cc) 运行未改动网络与 200 秒流量场景。驱动比原生测试类多要求一个 TCP 实现选择，因此补充 TcpNewReno；该基线只传 UDP。
- 每个派生场景读取同一原生动态转发表，跟踪从源站到目的站的实际路径。Skyfield/SGP4 按相应发射卫星的 TLE、时刻和大连站址计算传播距离、仰角、方位。OpenSatCom 0.7.0 的链路预算与 DVB-S2 曲线产出卫星到大连方向的有效速率。射频与物理层仿真在 chistarlink-repair:phase1 容器中运行。
- 每 100 ms 将有效速率写入原生 [GSL 带宽接口](https://github.com/snkas/hypatia/blob/0ac531c313eba2335f6344b46347140c3a0d4230/ns3-sat-sim/simulator/contrib/satellite-network/helper/gsl-if-bandwidth-helper.cc) 的实际发射卫星和网卡。Hypatia 自身按 SGP4 轨道更新各跳传播时延，其余地星/星间链路维持原生 10 Mbps。星地服务下行采用自由空间和理想化收发机曲线，PHY 输出的速率已含估计 BLER。
- ns-3.31 从 UDP 收包实测有效吞吐与交付率；时延由同一序号的收发事件相减，报告最近秩 P95。应用时长之外保留 0.5 秒排空窗口。

## 重放

在仓库根目录执行。评测主机需要 Python 3、Docker、curl，两个仿真容器运行时可离线。

```sh
python3 tasks/regression/build.py
docker build -t chistarlink-repair:phase1 -f tasks/repair/Dockerfile tasks/repair
```

公开评分支持只提交允许修改的字段。下面评分给定 JSON 文件，同时检查旧业务和新业务，返回 0 表示全部通过。

```sh
python3 tasks/regression/replay.py --task C01 --candidate candidate.json --output /tmp/c01.json --raw /tmp/c01-raw
```

维护者使用私有参考配置与独立场景执行完整矩阵。

```sh
python3 tasks/regression/replay.py --private tasks/regression/private --output /tmp/regression.json --raw /tmp/regression-raw
```

每题在主场景和独立留出场景分别运行旧工程＋旧需求、旧工程＋新需求、修改工程＋旧需求、修改工程＋新需求。期望依次通过、失败、通过、通过。共同门限为交付率至少 98%、P95 时延不超过 100 ms、口径不超过 0.35 m；各业务负载、吞吐下限及功率上限在任务清单中。详细的参考设计、留出参数、完整无线轨迹和逐包事件保存在本地评测材料中。

## 共用单链路回放

[network.py](network.py) 供链路设计和修复题调用，和上述多跳 Hypatia 子网使用同一 ns-3.31 镜像。它创建两个 IPv4 节点，逐样本调整传输设备速率和信道时延。UDP 应用以 1000 字节数据报持续提供业务，接收端按时间窗内收到的数据报统计。入口容量为零时丢弃新到业务，在途分组继续传播。队列深度为 4 个分组。输入每行给出同一有向链路的 time_s、link_id、rate_bps、delay_s，时间从零开始严格递增。

```sh
python3 tasks/regression/network.py --trace samples.csv --duration-s 10 --offered-mbps 1 --output /tmp/link-result
```

本次运行的 24 次判定、原生基线和镜像标识见 [公开测量记录](evidence/summary.json)。C03 另外保留[只降功率的对照配置](evidence/only-power.json)，可用公开评分入口独立运行。该设计满足 1 W 上限，但业务有效吞吐约 0.866 Mbps，低于 1.40 Mbps 要求。
