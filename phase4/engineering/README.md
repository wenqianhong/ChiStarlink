# NTN 多组件工程修改与原生重放

本批找到一个通过原生功能验收的射频子系统参考工程。它把地心坐标、地面终端局部坐标系、圆孔径天线、TR 38.811 传播损耗和频率选择性信道接在同一个 ns-3 事件循环。最终指标是接收 SNR 和传播增益。该例程没有承载端到端用户包。另有 OAI 的真实跨层故障记录与一次有限的 RFsim 启动实测。

## 已重放的参考工程

[ns-3 MR !1517](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/1517) 在 2024-05-26 合并。输入基线为 `a6b0d83a8fe03fbcf98a29213335d722e35cab10`。五个提交依次增加测试向量迭代、向量点积、38.811 信道、圆孔径天线和地心几何模型。可将原始工程任务表述为：为 VSAT 下行提供一套可实例化的 NTN 信道，连接卫星与终端的空间位置、天线增益、链路损耗、终端噪声与接收功率谱，输出可核验的时间序列；保留各组件的参考值测试。

| 实测版本 | 上游操作与结果 |
|---|---|
| 信道提交 `9a725b54` | 编译真实示例时缺少后续提交引入的地心模型头文件。该切面说明提交间的真实依赖。[原生日志](evidence/partial-build.txt) |
| MR 头 `2bbcec06` | 原生 NTN 传播测试通过。集成示例在本机容器未输出轨迹。上游另有后续修订记录。[传播测试](evidence/integrated/tests.txt) · [历史记录](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/1998) |
| 发布版 ns-3.42，`ab4cce02` | 原生地理坐标转换、圆孔径天线及 NTN 传播测试全部通过。官方默认郊区下行每 10 ms 采样一次，0 至 0.99 秒共 100 行。SNR 为 6.56241–14.5415 dB，传播增益为 −210.397 至 −210.396 dB。[结果](evidence/release/summary.json) · [原始轨迹](evidence/release/ntn-snr-trace.txt) · [原生测试](evidence/release/tests.txt) |

从仓库根目录执行。构建使用第二阶段 Ubuntu 工具链，并从上游下载固定源代码。运行期 Docker 禁用网络。输出目录须为空，因上游示例会追加到已有轨迹。

```sh
python3 phase2/oai/build.py
python3 phase4/engineering/replay_ns3.py release --out /tmp/chistar-ns3-42
python3 phase4/engineering/replay_ns3.py partial --out /tmp/chistar-ns3-channel-commit
```

## 值得继续复现的真实系统工程

| 来源 | 必须联动的组件 | 原生验收与目前证据 |
|---|---|---|
| [OAI !2893](https://gitlab.eurecom.fr/oai/openairinterface5g/-/merge_requests/2893) | RFsim 透明/再生载荷时延、多普勒演变、UE 时间同步及漂移 | 比较 gNB/UE 运行时间对齐与 LEO 接入。合并中有 18 个文件，本批追溯代码。 |
| [OAI !3194](https://gitlab.eurecom.fr/oai/openairinterface5g/-/merge_requests/3194) · [issue #901](https://gitlab.eurecom.fr/oai/openairinterface5g/-/issues/901) | gNB 公共 TA 漂移、UE 读取系统消息后再发起接入、UE RTT 与 RFsim 场景 | 原 issue 提供 UE 配置、日志、仪表侧抓包及 USRP B210 外部时钟条件。需检查 Other SI 解码与接入。实物仪表环境和仿真环境应分别记录。 |
| [OAI !3398](https://gitlab.eurecom.fr/oai/openairinterface5g/-/merge_requests/3398) | RFsim 卫星状态、gNB 连续广播 SIB19、UE 按历元更新 TA | 检查广播参数随时间更新及 UE 应用后的接入行为。17 文件变更已核对。 |
| [OAI !3663](https://gitlab.eurecom.fr/oai/openairinterface5g/-/merge_requests/3663) | SIB19 状态、上下行多普勒、RRC 重建、核心网用户面 | 原始合并版 CI 包含 UE IP、上下行各 20 包且丢包最多 5%、触发重建以及重建计数等于 1。中断期 ping 有独立的 80% 门限。[原版 CI](https://gitlab.eurecom.fr/oai/openairinterface5g/-/blob/9b0bb594f0c8603e6ab3bfa577e8bef25df18da4/ci-scripts/xml_files/container_5g_rfsim_ntn_leo.xml) |
| [srsRAN GEO 配置](https://github.com/srsran/srsRAN_Project/commit/b123bc8fefab7902b7202e537a0f94994770b754) · [固定原生 CI](https://github.com/srsran/srsRAN_Project/blob/9f3a3da13092b8623332d8362b864400b0176b2e/.gitlab/ci/e2e/zmq_ntn.yml) | srsGNB、NTN channel emulator、Amarisoft UE、Open5GS、Retina | 原生 ZMQ CI 引用 Amarisoft UE 与外部收发二进制，当前没有这些运行材料。保留候选。 |
| [SNS3 LoRa 卫星切换](https://github.com/sns3/sns3-satellite/commit/fb07919c3bd50ea2307592662c4c63b5e16b6320) · [原生测试提交](https://github.com/sns3/sns3-satellite/commit/36063d165df6f6bb99ed7bb1d9260396a441db23) | 移动 UT MAC、卫星 LoRa 设备、周期发送器、网关、网络服务器和 ACK | 上游断言包含网关收包与三组终端接收时间。查到具体实现和测试；本目录未执行 SNS3。 |

[四个 OAI 合并的固定版本与逐文件清单](evidence/oai-merge-metadata.json)

## OAI RFsim 启动实测

在第二阶段固定的后续 OAI 提交 `cb98db5b` 构建真实 gNB、UE、RFsim 和编码库。两个进程在同一隔离容器内运行，上游 LEO 配置仅调整本地通信地址，gNB 启用轨道选项。双方分配 SAT_LEO_TRANS 并报告 20 ms、153600 个样本。测试没有部署 5GC，gNB 的 AMF SCTP 连接被拒，未取得 UE IP、重建计数或双向用户包，因此 !3663 仍是待复现候选。进程退出码包含脚本清理动作。[日志摘录与实际参数](evidence/oai-rfsim.json)

```sh
docker build -t chistarlink-oai:ntn-rfsim phase4/engineering
mkdir -p /tmp/chistar-oai-loop
docker run --rm --network none -v /tmp/chistar-oai-loop:/logs -v "$PWD/phase4/engineering/rfsim_pair.py:/run.py:ro" chistarlink-oai:ntn-rfsim python3 /run.py --out /logs/kepler --orbital --timeout 45
```
