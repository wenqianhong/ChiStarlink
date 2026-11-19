# NR PDSCH 波形标定

本模块通过 OAI 原生 nr_dlsim 产生条件化 BLER 表。每次试验包括发送端 LDPC 编码、资源映射与 OFDM、复高斯噪声、接收端解调和译码。在下游任务里，轨道和链路预算按每个时间样本给出到达终端的 C/N₀；适配器用该时刻的链路条件查询表，再把有效速率交给 ns-3。标定时信道为 AWGN，几何演变、残余多普勒、同步丢失、接入流程和波束切换需分别分析其模型边界。

## 运行方式

从仓库根目录运行以下命令。构建需要联网获取固定源码、Ubuntu 基础镜像和依赖包。每个源码归档在构建前校验 SHA-256。波形标定容器以 --network none 执行。

```sh
python3 phase2/oai/build.py
python3 phase2/oai/calibrate.py point --prbs 5 --mcs 12 --snr 4.5 --trials 200 --seed 723481 --output /tmp/oai-point
python3 phase2/oai/calibrate.py sweep --workers 4 --output /tmp/oai-sweep
```

完整实测的 [curves.csv](curves.csv) 逐点列出 TBS、计数、BLER 和二项比例 95% Wilson 区间。对应的 [measurements.jsonl.gz](measurements.jsonl.gz) 含每次运行的命令行、独立种子、原生 CSV、标准输出和该日志的 SHA-256。改变任务射频条件会重新计算 C/N₀、分配内 SNR 和有效吞吐。

## SNR 与速率口径

- 对应全尺寸 NR 载波内的 **PDSCH 调度分配**。每点仅一层、一个收发天线、正常 CP、15 kHz 子载波间隔、一个全长下行时隙。表内 PRB 数表示该次 PDSCH 实际占用的资源。载波配置与分配分别由 -R 和 -b 记录。[OAI 原生模拟入口](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/cb98db5b5d2d95c86673821bfc9fa1be9e225b97/openair1/SIMULATION/NR_PHY/dlsim.c)
- SNR 是解调前的分配内信噪比。模拟器从发射符号测量平均时域功率，以 FFT 大小除以 12×已分配 PRB 的比例归一化，再按命令行 SNR 设置噪声方差。因此对于单层、分配内总接收功率和白噪声，SNR[dB] = C/N₀[dB-Hz] − 10 log₁₀(12×PRB×15000)。输入 C/N₀ 必须对应本用户分配到的功率。[OAI 噪声归一化](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/cb98db5b5d2d95c86673821bfc9fa1be9e225b97/openair1/PHY/TOOLS/signal_energy.c)
- 配置一个传输轮次。nr_dlsim 的 eff_rate 在解码器报告成功时累加 TBS。planned_trials 为已调度的传输块总数。active_trials 为 UE 实际激活 PDSCH 的轮数，decoded_tbs 为完成正确解码的块数。在低 SNR 下可能无法激活传输块，此时 PDCCH 等控制环节亦影响实际交付。表中用于服务速率的 bler 是面向全部已调度块的未交付比例。active_crc_bler 单独保留上游已激活块的报告口径，分母为零时 CSV 留空。errors = 试验数 − round(eff_rate×试验数/TBS)，bler = errors/trials。reported_errors 另存上游 n_errors_0 计数；其源码使用 LDPC 迭代次数判据。TBS 是单次实际调度的传输块位数，已包含对应资源映射对可用净数据的限制。
- 每个调度时隙的有效位数取 TBS×(1−BLER)。业务层时间平均速率还需乘每秒实际调度的此类下行时隙数。μ=0 对应 1 ms 时隙。上游模拟 TDD 例子在 10 ms 周期内有 7 个完整 DL 时隙，另有混合时隙。若只使用完整 DL 时隙，可按每秒 700 个调度；若任务采用独占、持续可调度的单向服务链路，应显式记录 1000 个/秒这一外部假设。[OAI 场景的 TDD 配置](https://github.com/OPENAIRINTERFACE/openairinterface5g/blob/cb98db5b5d2d95c86673821bfc9fa1be9e225b97/openair2/GNB_APP/gnb_config.c)
- 每个网格点使用多组显式 OAI_RNGSEED，聚合噪声试验。区间描述固定接收机和 AWGN 条件下的计数不确定性。不同物理参数的表不可混合；门限附近优先使用独立种子的离网格直接重放。BLER 已进入服务速率时，网络层不应再次据此丢同一批块。

## 标定范围与独立检验

固定 OAI 提交 cb98db5b5d2d95c86673821bfc9fa1be9e225b97，在 25 PRB 载波上标定 2、5、8、11 PRB 的 PDSCH 分配，MCS 表 0 选 4、8、12、14、16、18、20、26，共 32 种配置。两轮各 100 个 TB/点，使用互不重复的噪声种子。粗网格覆盖 −20 到 +30 dB。分别对每个配置取相邻粗测点，若未交付率相差超过 0.08，则在该段以 0.25 dB 重新实测，并纳入两侧各一个邻点。最终曲线上 1,089 点来自 217,800 次调度。其中 123 个点的 200 次调度均未激活 UE 的 PDSCH，这些点的条件 CRC BLER 留空。固定的物理层参数还包括 LDPC 最大迭代 5、一个调度层、时隙号 1，未开启 PTRS 或 HARQ 重传。

独立检验从每条曲线选择预计约 50% 未交付率的相邻点，取二者之间从未建表的 SNR，并用新的种子直接重放 400 个 TB。32 次验证共 12,800 个 TB，插值与实测的未交付率绝对差中位数为 0.03125，最大为 0.105。最大偏差出现在 8 PRB、MCS 26、19.625 dB。临界验收应考虑这些误差。[独立校验计数](validation/summary.json) · [独立运行原始数据](validation/measurements.jsonl.gz)

```sh
python3 phase2/oai/validate.py --curves phase2/oai/curves.csv --output /tmp/oai-validation
```
