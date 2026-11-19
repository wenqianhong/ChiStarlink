# 三道跨层修复题

这组三题把公开工程的原生模型连接成一条移动星地服务下行，然后对三个不同接口分别注入缺陷。每题从自己的 `adapter.py` 开始，允许修改的范围由同目录 `task.json` 确定。三题均标记为**合成故障**。上游源码、任务输入、参考修改和测试属于不同材料。参考修改及留出场景保存在本地评测目录。

| 题号 | 输入工程的现象 | 检查的接口 | 正常场景 |
| --- | --- | --- | --- |
| R01 | 星历导出格式改变后，卫星在站点上空，应用却收不到包 | 星历角度进入仰角门限 | 原有 deg 数据源 |
| R02 | 部署短标签终端后，链路余量和收端业务消失 | 设备描述进入接收端极化、链路预算和调制解调 | 使用标准全称的终端 |
| R03 | 调制解调器输出正常，分组到达率却显著下降 | 遥测速率进入 ns-3 设备的 bit/s 配置 | 原有 Mbit/s 速率字段 |

## 原生来源与模型边界

- Hypatia 的旧版 25 × 25 Starlink 星座文件中第一个两行根数（TLE），给出模型化轨道。固定快照与源路径见 `scenario.json`。时间从该 TLE 的历元起算。[轨道输入](https://github.com/snkas/hypatia/blob/0ac531c313eba2335f6344b46347140c3a0d4230/paper/satellite_networks_state/input_data/legacy/starlink_tles_25x25.txt)
- Skyfield 1.54 用 SGP4/WGS84 计算每秒的站心角和斜距。OpenSatCom 0.7.0 原生计算自由空间损耗、天线与接收噪声、极化损耗及 Eb/N0。固定 QPSK 1/2 的 DVB-S2 解析误块曲线产生有效速率，单用户流量充足时其原生调度器输出可用服务容量。固定编码方式使三题的接口错误能够单独归因。[OpenSatCom 版本](https://github.com/jman4162/opensatcom/tree/afb59de6b28614d6db23f7969bc1932226a98dcc)
- 可用容量和斜距除以光速所得的传播时延，每秒重新注入由 Hypatia 所带 ns-3.31 构建的 IPv4/UDP 点对点设备。固定发送负载为 1 Mbit/s，共 12 秒。验收读取接收端数据包和时戳。窗口结束后到达的包不计入该窗口的交付。
- 模型覆盖一条服务下行与一个 UDP 接收业务。它采用有效速率抽象，未模拟实际运营系统的空口、NR PDSCH 波形、HARQ、馈电链路、星间多跳路由。

## 重放

从仓库根目录构建一次两个镜像。两道构建命令分别锁定 Python 依赖与 ns-3/Hypatia 源码。评测时容器关闭外部网络。

```sh
docker build -t chistarlink-repair:phase1 tasks/repair
python3 tasks/regression/build.py
```

下面两条命令分别运行 R01 的故障触发和保留场景。目标判定失败时命令以状态 1 退出；日志继续保留。评测其他候选修复时使用 `--adapter /path/to/adapter.py`。

```sh
python3 tasks/repair/replay.py R01 --case target --output /tmp/chistarlink-repair-target
python3 tasks/repair/replay.py R01 --case regression --output /tmp/chistarlink-repair-regression
```

每次产生的 `layers.csv` 记录轨道、仰角、准入结果、极化、射频、调制编码和服务容量，`trace.csv` 是 ns-3 输入，`metrics.json` 是原生分组仿真输出，`judgment.json` 记录每条断言的结果。三题适用相同业务需求：接收比例至少 99%、有效吞吐至少 0.99 Mbit/s、端到端第 95 百分位时延至多 15 ms。这些是为合成题定义的验收门限。各题还检查自身的接口契约、时间样本数和传播时延。额外使用线性域 Friis 传输公式及热噪声谱密度独立核对每个时刻 C/N₀，允许 0.02 dB 误差。

本地评测目录保留修复后的三个文件 `R01.py`、`R02.py`、`R03.py` 与 `holdout.json`。下面的完整验收重新模拟 18 组输入，按照应用实际接收判断每题的目标、回归、留出六格。留出场景改变站点、过境时间、带宽和终端极化。

```sh
python3 tasks/repair/verify.py --private tasks/repair/.private --output tasks/repair/.private/full
```

## 上游交叉检查

将 OpenSatCom 检出到下例路径，在同一个运行镜像内执行上游的网络、DVB-S2 和 SGP4 用例。原生测试输出在 `evidence/upstream-tests.txt`；SGP4 上游测试计入依赖核查，正式任务轨道坐标采用 Skyfield。

```sh
git clone https://github.com/jman4162/opensatcom /tmp/chistar-upstream-repair
git -C /tmp/chistar-upstream-repair checkout afb59de6b28614d6db23f7969bc1932226a98dcc
docker run --rm --network none -v /tmp/chistar-upstream-repair:/native:ro -w /native chistarlink-repair:phase1 python -m pytest -q -p no:cacheprovider tests/unit/test_network_sim.py tests/unit/test_dvbs2.py tests/unit/test_sgp4_provider.py
```

## 第一阶段实测

两套 Docker 镜像完成全部 18 组判定。三道题的正常场景在故障版与修复版均通过，变化场景在故障版均发生业务退化，参考修改后全部通过。每个公开触发场景发出 1500 个 UDP 应用包。

| 任务 | 修复前收包 | 修复后收包 | 修复后吞吐 | 修复后 p95 |
| --- | ---: | ---: | ---: | ---: |
| R01 仰角接口 | 0 | 1500 | 1.000 Mbit/s | 5.603 ms |
| R02 极化描述 | 0 | 1500 | 1.000 Mbit/s | 5.603 ms |
| R03 速率导出 | 3 | 1500 | 1.000 Mbit/s | 5.603 ms |

公开目标场景的逐层 CSV、ns-3 原始指标和详情在 [evidence/target](evidence/target)。[18 组判定摘要](evidence/results.json) 包含结果摘要与判定文件指纹。R03 参考方案另行独立重跑一次，两个 CSV、原生指标和判定 JSON 均逐字节一致。
