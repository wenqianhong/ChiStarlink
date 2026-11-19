# 34 道全链路设计派生题

D101–D134 由第二阶段的 D01–D04 四道母题派生。34 道题采用不同的合成终端、过境时刻和业务参数，涵盖选站、时段预约、功率与编码、低噪声接收、天线跟踪、PRB 分配、馈线与增益、下行配额、终端编码目录九组工程设计。站点取具名城市的近似坐标，统一以海拔 0 m 建模。星座输入取 Hypatia 的同一合成 TLE，所有波形曲线复用第二阶段经验证的 OAI 表。

[题干与模块约束](catalog.json) · [公开项目输入与可编辑字段](specs.json) · [分场景实测证据](evidence/matrix.json)

## 公开入口

在仓库根目录运行。主机需要 Python 3.9+、Docker CLI 和可用的 Docker daemon。使用第一、二阶段已有镜像和已入库的实测曲线；新机器可按下列命令构建仿真器。

```sh
docker build -t chistarlink-repair:phase1 tasks/repair
docker build -t chistarlink-itur:phase2 phase2/propagation
python3 tasks/regression/build.py
```

以 D105 为例，第一条命令重放题目附带的初始工程。其预期结果为主窗口未达标，退出码 1。下面的命令会从 specs.json 导出这个样本的起点和可编辑设备目录。

```sh
python3 phase3/design/replay.py D105 --output /tmp/chistar-d105-initial
python3 - <<'PY'
import json
from pathlib import Path
s = next(x for x in json.loads(Path("phase3/design/specs.json").read_text()) if x["id"] == "D105")
Path("/tmp/chistar-d105-answer.json").write_text(json.dumps(s["initial"], indent=2))
print(s["description"], s["choices"])
PY
```

从目录中选择配置并修改自己的 answer.json。主窗口使用题面负载，独立回归窗口使用 0.15 Mbps 业务。通过退出码为 0；两次运行分别生成 radio.jsonl、trace.csv、metrics.json 和 judgment.json。

```sh
python3 phase3/design/replay.py D105 --candidate /tmp/chistar-d105-answer.json --output /tmp/chistar-d105-target
python3 phase3/design/replay.py D105 --candidate /tmp/chistar-d105-answer.json --profile regression --output /tmp/chistar-d105-regression
```

## 约束如何传递

- TLE 和站址进入 Skyfield。接入门限和预约时刻控制本秒链路是否可见及其距离。初始、主参考及留出场景使用相同的输入工程接口。
- OpenSatCom 的自由空间预算包含发射功率、馈损、天线口径和指向误差，结合接收噪温计算 C/N₀。阶段二的 ITU-R P.676-12 接口按频率与仰角扣除晴空气体衰减。
- 使用 OAI 单层 NR PDSCH AWGN 的实测 PRB、MCS、SNR、传输块大小和误块计数。默认单向专用下行每秒 1000 个时隙，配额题把每秒可用时隙数折为平均速率；包级网络不模拟逐槽 TDD 突发。误块率已折入容量，业务层直接以本秒容量运行。
- ns-3.31 的单向 IPv4/UDP 包级仿真每秒更新容量、传播时延并记录有效吞吐、交付率和 p95 时延。每题同时约束峰值和平均射频功率、口径、带宽和 EIRP。此组衡量单条星地服务链路的任务表现。

## 录取与复核

每题执行主窗口初始失败、主窗口参考通过、独立过境窗口初始失败、独立过境窗口参考通过及低负载回归参考通过五次重放。主窗口与留出窗口对应相隔至少一小时的不同过境事件。34 个候选均符合矩阵预期，共 170 次逐包重放。审计根据原始 OAI 计数独立重算有效样本的 SNR、插值 BLER 和速率，并逐行对照 ns-3 实际输入，共核验 3720 个无线采样点。

完整判定、原始轨迹、留出窗口与参考配置由受信评测器保存在本地 private/。持有这些材料时可以重新运行 170 格矩阵并复核入库证据。

```sh
python3 phase3/design/verify.py --workers 3
python3 phase3/design/release.py
```

## 发布抽查

在只含 Git 已跟踪文件和本组公开交付物的临时目录中，D105 初始运行的无线轨迹 SHA-256 和每项判定均与公开矩阵一致。仅从公开设备目录选择的另一组候选配置在主窗口和低负载回归中通过，越界口径和布尔型功率被入口拒绝。[公开入口黑盒记录](evidence/public-blackbox.json)

PyEphem 4.2.1 使用相同 TLE、台站和 UTC 时刻，关闭大气折射后，独立复算整组的 3720 个斜距、仰角和指向。最大距离差 62.60 m，三维视线夹角最大差 0.00856°，356 个零接入采样的判断均相符。审计逐格复算设备目录、峰值及平均功率、EIRP 和频谱等约束，并从 ns-3 已接收的固定长度 UDP 包数复算有效吞吐及交付率。p95 时延使用原生 ns-3 接收端统计值与相应任务门限比较。[全矩阵独立校验](evidence/cross-check.json)

持有受信参考与逐层原始数据时，在安装 ephem==4.2.1 的 Python 环境中执行：

```sh
python3 phase3/design/audit.py
```
