# 四个完整链路设计任务

D01 选择接收站及接入仰角，D02 设计受限功率下的调制编码配置，D03 联合选择天线口径和跟踪精度，D04 在固定总功率下分配带宽与编码。每题的输入工程由 tasks.json 的 initial、radio、station、TLE、起止时刻和业务流组成。候选答案是只含 choices 中可编辑字段的 JSON。任何满足门限的目录内配置均可得分。

## 来源及模型边界

- 轨道输入来自 [Hypatia 固定版本的 legacy 合成星座](https://github.com/snkas/hypatia/blob/0ac531c313eba2335f6344b46347140c3a0d4230/paper/satellite_networks_state/input_data/legacy/starlink_tles_25x25.txt)，四题均取第一颗模拟卫星。站址、业务窗口、资源目录与 QoS 门限由本项目定义，属于同一家族的四道派生题。地面站的经纬度采用 tasks.json 固定值。
- Skyfield 1.54 将 SGP4 结果转换到接收站的拓扑坐标，每秒计算一次方位、仰角和距离。门限以下按零容量处理。总时长 30 秒，采用逐秒零阶保持的服务过程。
- [OpenSatCom v0.7.0](https://github.com/jman4162/opensatcom/tree/afb59de6b28614d6db23f7969bc1932226a98dcc) 提供原生自由空间损耗、链路预算、DVB-S2 ModCod 目录与解析 BLER 曲线。每一候选档独立计算 Eb/N0，取预计有效速率最高者。这是明确的物理层抽象，假设载波同步完成、晴空且无干扰。没有执行 MATLAB NR 波形、真实设备或星间网络测量。
- 本项目的接收机增益由口径和效率计算，跟踪误差用高斯主瓣损耗估算。[MATLAB Workshop 练习 2–4](https://github.com/MikeMcLernon/SatCom-Workshop-/tree/59725cfd4e25d90a83216e78398b89f2db10e7ae) 是接入、链路预算与方向图设计的背景参考。本批源工具原生复验具体落在 OpenSatCom 的预算及调制解调器单测。
- 服务层用 Hypatia 配套 ns-3.31 执行一个卫星发送端到地面业务接收端的点对点 IPv4/UDP 流。GSL 的速率和传播时延逐秒更新。PHY 曲线已把块错误折入可用速率。该场景衡量单段下行的逐包交付、吞吐和时延，研究范围不含星间路由或完整星座多跳连接。统计窗口为 [0, 30 s)，窗口外到达的包不计入交付。

### 每题的材料对应

| 任务 | 原始材料 | 本项目派生的要求与验收 |
| --- | --- | --- |
| D01 | Hypatia 的合成 TLE、原生距离计算，以及 Workshop 的星地接入练习 | 把接入窗口转成候选站选择问题，测量最小仰角约束下的 UDP 业务。 |
| D02 | OpenSatCom 的 [链路预算输入及参考测试](https://github.com/jman4162/opensatcom/blob/afb59de6b28614d6db23f7969bc1932226a98dcc/tests/unit/test_link_engine.py) | 以功率目录代替无限制的升功率，给接入端固定带宽并设置端到端吞吐门限。 |
| D03 | Workshop 的链路及方向图练习，OpenSatCom 的固定增益天线接口 | 将口径和指向偏差转成实收增益，按受限口径和功率下的数据交付情况验收。 |
| D04 | OpenSatCom 的 [调制解调器测试](https://github.com/jman4162/opensatcom/blob/afb59de6b28614d6db23f7969bc1932226a98dcc/tests/unit/test_modem.py) 及 [DVB-S2 工作点](https://github.com/jman4162/opensatcom/blob/afb59de6b28614d6db23f7969bc1932226a98dcc/src/opensatcom/modem/dvbs2.py) | 给定频谱目录和总功率，用每档数据率换算 Eb/N₀ 并测量包级吞吐。 |

## 从初始工程重放

从仓库根目录先按照 tasks/repair 与 tasks/regression 的说明构建两个镜像。默认主机只需 Python 标准库与 Docker CLI。下列命令会执行初始方案，预期产生未达标判定（退出码 1）；运行故障会抛出异常。

```sh
python3 tasks/design/judge.py D01 --output /tmp/chistar-d01-initial
```

将允许修改字段保存到自己的 candidate.json 后，执行目标与邻近时段低负载回归。成功退出码为 0。具体时延、吞吐、交付率门限见 tasks.json；回归在前 30 秒以 0.15 Mbps 发包，最小有效吞吐为 0.14 Mbps，并保留同题的交付率和时延要求。

```sh
python3 tasks/design/judge.py D01 --candidate candidate.json --output /tmp/chistar-d01-target
python3 tasks/design/judge.py D01 --candidate candidate.json --profile regression --output /tmp/chistar-d01-regression
```

每次运行重新生成 radio.csv（几何、C/N₀、Eb/N₀、解析 BLER、档位、容量和时延）、trace.csv（ns-3 实际输入）、metrics.json（业务统计）和 judgment.json（布尔断言）。参考解与留出时段在本地 private/ 独立保存；公开目录包含输入、验收程序和汇总证据。

## 原生测试

在固定提交的 OpenSatCom 源工程中使用与任务相同的无线镜像运行下列命令。18 个预算、模式表及调制解调器测试通过。上游可选相控阵测试在未安装 PAM 时采用峰值增益，四道设计题均使用这里明确建模的抛物面口径模型。另有 4 个本地测试独立检查距离翻倍、功率翻倍、仰角门限与误块折算。

```sh
python -m pytest -q tests/unit/test_link_engine.py tests/unit/test_modem.py tests/unit/test_dvbs2.py
# 在本仓库 tasks/design 目录，同一个无线镜像内执行
python -m pytest -q test_radio.py
```

## 几何交叉检查

validate_geometry.py 直接调用 Hypatia 原始 satgenpy 的台站至卫星距离函数，与 Skyfield 在相同 UTC 时刻、TLE 和站址计算的距离比较。固定的 4 个任务窗口、4 个候选站和 30 个采样时刻共 480 点，包含地平线以下样本。以单程传播时延误差小于 0.01 ms 作为检查上限。具体数值见 evidence/hypatia-geometry.json。验证环境使用 Skyfield 1.54、ephem 4.2.1 和 geopy 2.4.1。

```sh
python tasks/design/validate_geometry.py /path/to/pinned/hypatia
```
