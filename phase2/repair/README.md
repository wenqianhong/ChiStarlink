# R01–R03 跨层修复复验

沿用第一阶段的站点、模型化 Starlink 根数、故障输入、参考补丁、业务负载与门限。二阶段保留原来三条待修复接口，重算每个时刻的无线和网络结果。

1. Skyfield 将固定 TLE 传播到站心斜距与仰角。R01 的错误发生在接入选择器，其星历真值继续用于物理预算。
2. OpenSatCom 计算自由空间预算、极化失配与 C/N₀。P.676-12 晴空气体斜路径衰减按当时仰角扣减一次。R02 的短标签极化处理位于预算之前。
3. 使用 OAI 原生 `nr_dlsim` 归档的单流 PDSCH AWGN 数据。单用户的可用发射功率全部分配给当次 PDSCH 资源。根据允许带宽选择实测 PRB 数，由传播后的 C/N₀ 扣除占用带宽的 dB-Hz 得到 SNR，在实测两点之间插值已调度传输块的成功率。用于业务容量的失败计数包含本次调度未成功交付的块；低 SNR 下可包括控制信道未检出。原始条件 PDSCH 计数另见标定证据。专用单向链路按 μ=0 的每秒 1000 个可调度下行时隙计，对有效容量施加 100% 下行占空比假设。使用候选 MCS 4、12、20，在已测配置中选择传输块有效速率最大者。R03 的速率单位映射位于 PHY 有效速率和网络设备之间。
4. ns-3.31 按秒应用单向点对点容量和传播时延，向接收端发送 1 Mbit/s 的 UDP 应用负载共 12 秒。目标门限沿用交付率 ≥99%、吞吐 ≥0.99 Mbit/s 和 p95 时延 ≤15 ms。检查器从原始 OAI 计数再次计算插值 BLER 和 TBS/时隙有效速率，并核对逐秒网络输入。

全链路范围为随轨道变化的一条星地服务下行。物理层用实测曲线进行链路抽象；接收的 UDP 分组使用已折算误块的有效服务容量。本组不模拟 NR 接入状态机、OAI RFsim、真实运营系统参数或多跳 ISL。

## 展开验收

需先构建 [ITU 容器](../propagation/README.md)、准备 [OAI 标定表](../oai/) 并构建第一阶段 [ns-3 容器](../../tasks/regression/README.md)。从仓库根目录执行单题或全矩阵。单题门限失败返回状态码 1；目标与回归样本的指标均保存在指定目录。无实测 SNR 区间覆盖时，程序报错并停止，避免外推。

```sh
python3 phase2/repair/replay.py R02 --case target --output /tmp/chistarlink-r02-p2
python3 phase2/repair/replay.py R02 --case regression --output /tmp/chistarlink-r02-normal-p2
python3 phase2/repair/verify.py --private tasks/repair/.private --publish-evidence
```

第一阶段本地评测材料中的 R01.py、R02.py、R03.py 与 holdout.json 仍为完整六格验收所需输入。公开发布内容仅含触发场景的逐层证据和汇总断言。

## 用独立波形运行检验插值

R03 目标场景第一秒的实际 SNR 为 14.8653 dB。第一版 14 至 16 dB 的粗网格虽能通过包级业务验收，独立 14.9 dB 试验中却仅有 7/300 个调度块未交付，远低于插值的 40.15%。此误差触发了瀑布区加密。[初版探针记录](evidence/coarse-grid-offgrid.json)

`offgrid.py` 从当前目标证据读取实际 MCS、PRB 和工作点，用额外种子直接调用 OAI 进行 300 次波形试验。针对最终表，测试采用未入表的 14.87 dB 位置。比较直接测量的 Wilson 区间与两个端点 Wilson 边界的线性插值。后者是插值一致性诊断，无法给出对整个连续区间的覆盖保证。

```sh
python3 phase2/repair/offgrid.py
```

在冻结表 `3a8cc5db…` 上，18 次逐层重放全部得到预期结果。每项测试发送 1500 个应用包，R01 与 R02 在故障版本的目标场景收到 0 包，R03 收到 6 包。三道参考修改都收全 1500 包，目标吞吐均为 1.000 Mbit/s，p95 延迟均为 4.141 ms。[逐项判定](evidence/summary.json) · [触发场景原始逐层与分组数据](evidence/target)

加密后，14.87 dB 独立探针 300 次有 16 次未交付，实测 5.333%，表格插值 5.080%，绝对差 0.253 个百分点。直接试验的 95% Wilson 区间为 3.31% 至 8.49%。[独立对照](evidence/offgrid/comparison.json) · [独立 OAI 原生日志](evidence/offgrid/measurements.jsonl.gz)
