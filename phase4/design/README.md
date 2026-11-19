# SNS3 多波束接入、星上转发与业务连续性

本目录收集能从上游需求、场景、协议实现一路追到业务计数的工程。评估单位是一个完整上游问题。改变流量、波束编号或随机种子仅用于同一道题的验证。

## 可复跑的原生工程

| 工程 | 需要贯通的约束 | 可采集的验收依据 |
| --- | --- | --- |
| GEO 多波束甚高吞吐卫星（VHTS） | 场景提供 72 束天线方向图，选取波束 1、8、20，分别挂接网关 1、2、3。每束 2 个终端、每终端 2 个业务用户。前向链路承载 G.711 和 HTTP，返向经过资源请求、NCC 分配与随机接入。 | 四段链路前馈、前向用户、返向用户、返向馈电的 SINR，资源请求与实际授予，终端应用吞吐。[原始工程](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/examples/sat-vhts-example.cc) |
| TN9 回传容量分配 | 波束 18 上 220 个终端产生开关业务，原生 XML 约束 13.75 MHz 帧结构。默认以 RBDC 分配容量，控制消息通过时隙 ALOHA 上报。 | 保留上游默认 300 秒运行，联合核对应用吞吐、资源授予和接入统计。[原始工程](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/examples/sat-dama-onoff-sim-tn9.cc) |
| 多星再生与星间链路 | 双星、星上网络层再生、星间转发、正返向 CBR。拓扑与路由直接来自工程。 | 端到端收发、各层统计和 ISL 丢包指标。[场景](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/examples/sat-constellation-example.cc) · [原始合并与 139 项文件改动](https://github.com/sns3/sns3-satellite/commit/174f9f2e4cf67a11ec81ccd2e9e277eda9aa0145) |
| 移动终端与网关切换 | 终端移动后，卫星、波束、网关与用户层的业务统计要同步迁移。另一系统用例在两颗 LEO 卫星间切换并约束五个接收端的损失。 | 上游逐点判定，8 秒和 18 秒分别检查 1-35、2-20 两束的吞吐，另核对 MAC、网关、卫星和终端计数。[断言](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/test/satellite-handover-test.cc) · [原始合并与 219 项文件改动](https://github.com/sns3/sns3-satellite/commit/9dc8f3522a690ea1358dd2ff784ccde567b0de33) |
| 星上再生 LoRaWAN | LoRaWAN 上行、馈线、网关、下行 ACK 与 RX1/RX2 时窗联动，还覆盖重复传输、星间和切换。 | 系统测试直接捕获 MAC 包事件，断言时窗、接收字节和切换前后指定波束的 ACK。[断言](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/test/satellite-lora-regenerative-test.cc) · [原始合并与 297 项文件改动](https://github.com/sns3/sns3-satellite/commit/49bdea49607f2fb9fc303fdac003d168946540dd) |

三个合并的一号父提交分别是 `72aa513f43b7`、`c9ec0614ec1d`、`202c72edfd3e`。本轮固定 SNS3 3.48（`2c0c6d4d7fd1`）与 ns-3.48。历史父提交的构建、失败复现、补丁回放仍需单独验证。GEO、双星 LEO 与公开 DVB/LoRa 配置分别表征不同系统，阶段数据不能推断商用 Starlink 的私有空口性能。

## 已取得的测量

| 原生工程或套件 | 本轮结果 |
| --- | --- |
| 三波束 VHTS | 前向应用 763.594 kbps，三个网关分别为 254.621、254.699、254.673 kbps。六终端发出 129 次 RBDC 请求，记录 1,422 次授予，单次 646–1,976 字节。HTTP 网页加载平均 3.6111 秒。应用抖动标量为 NaN，未作为验收指标。 |
| TN9 默认 220 终端，300 秒 | 返向应用 3,414.43 kbps，110,465 次 RBDC 请求，1,037,080 条授予采样（含零授予）。时隙 ALOHA 碰撞率 9.85968%，数据帧 0/1/2 的符号分配率为 95.9314%、97.4923%、94.4755%。[样本数与哈希](evidence/tn9.json) |
| 双星星间转发 | 30 秒，前/返向应用 3,647.70/3,708.92 kbps。1→2 和 2→1 两个方向分别记录 9,776 和 18,961 个 ISL 丢弃率样本，各方向的丢弃计数和均为 0。 |
| 网关切换 | 100 秒，前/返向应用 204.959/204.632 kbps。独立的上游切换系统套件 2/2 通过。场景 1 在 8 秒测得波束 1-35、2-20 的吞吐分别为 40.96、0 kbps，到 18 秒为 0、40.96 kbps。 |
| LoRaWAN 切换 | 100 秒，上行应用 0.117805 kbps，下行应用字节为零。MAC 层的下行 ACK 由独立上游系统套件验证，7/7 通过，包括时窗错过、双星转发和切换。 |

TN9 官方默认在波束 18 运行，但源码显式选用波束 1 的外部衰落索引。220 终端在本机 8 GB Docker 虚拟机使用 glibc 分配器时遭 OOM 终止；安装并预加载 Ubuntu 的 libjemalloc2 后完成全部 300 秒，保留默认业务、窗口和接入配置。另以 64 终端跑 300 秒测得 1,013.32 kbps 和 2.27137% 碰撞率，此工况单独记录。

VHTS 用相同种子和参数独立启动两次，四段 SINR、请求、授予及应用吞吐原始文件的 SHA-256 均相同。按包重复采样的 SINR 中位数依次为前向馈电 14.5186 dB、前向用户 12.384 dB、返向用户 15.657 dB、返向馈电 11.2575 dB。资源授予按事件记数，无法据此推断 TBTP 控制包的精确个数。

[实测指标、记录数与哈希](evidence/vhts.json) · [精简原始输出](evidence/raw) · [网关与终端切换测试日志](evidence/sat-handover-test.log) · [LoRaWAN 测试日志](evidence/sat-lora-regenerative-test.log)

## 复跑

在仓库根目录运行。首次构建下载约 1.3 GB 官方场景、方向图和测试输入，以及源码归档。程序核验归档 SHA-256 和每个数据文件的 Git blob ID。镜像内工作目录为 `/src`。将输出挂载到新建空目录，避免不同试验混用。

```sh
python3 phase4/design/build.py /tmp/chistarlink-sns3-build
mkdir -p /tmp/chistarlink-sns3-results
docker run --rm --network none \
  -v "$PWD/phase4/design/replay.sh:/replay.sh:ro" \
  -v /tmp/chistarlink-sns3-results:/out \
  chistarlink-sns3:3.48 sh /replay.sh /out
```

在宿主机运行 `python3 phase4/design/measure.py /tmp/chistarlink-sns3-results/vhts` 可重算 VHTS 指标。单独复跑 TN9 的容器命令如下。

```sh
docker run --rm --network none -v /tmp/chistarlink-sns3-results:/out chistarlink-sns3:3.48 sh -ec '
  mkdir -p /out/tn9-full
  allocator=$(ldconfig -p | awk "/libjemalloc.so.2/{print \$NF; exit}")
  LD_PRELOAD="$allocator" build/contrib/satellite/examples/ns3.48-sat-dama-onoff-sim-tn9 --OutputPath=/out/tn9-full
'
```

## 可继续挖掘的其他入口

- 前向跳波束示例同时给出图案、发射时序及波束负载。要制成设计题，应先检查终端分配、业务流启动时间与每束排队情况，再设定服务门槛。[SNS3 示例](https://github.com/sns3/sns3-satellite/blob/2c0c6d4d7fd1628eda1b923a7e135749513769fa/examples/sat-fwd-link-beam-hopping-example.cc)
- OpenSAND 可将真实 Linux 应用接入卫星仿真网络，适合检查应用/队列、DAMA 与回传容量分配之间的相互作用。当前目录没有 OpenSAND 的运行证据。[CNES 工程](https://github.com/CNES/opensand) · [体系结构](https://www.opensand.org/overview.html)
- 5G-LENA 的 NR 仿真适合另一类端到端调度、传播与应用问题。后续需要独立固定 ns-3 与 NR 模块版本，选定 NTN 示例和信道配置。[官方示例索引](https://cttc-lena.gitlab.io/nr/html/group__examples.html)
