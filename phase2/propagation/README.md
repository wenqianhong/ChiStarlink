# 第二阶段晴空气体吸收

所有任务使用 ITU-Rpy 0.4.0，在 P.676-12 附录 2 的斜路径近似模型中按实际仰角计算气体衰减。载频用 Hz 输入，转换为 GHz 进入原生库；输出为 dB，逐链路、逐采样时刻从自由空间预算所得 C/N₀ 扣减一次。默认场景的地面气压为 1013.25 hPa、温度为 288.15 K、水汽密度为 7.5 g/m³、柱积分总水汽为 15 kg/m²，站高为 0 km。这些数值定义合成晴空场景。模型未加入雨、云或闪烁。对本批观测窗，角度范围为 5° 至 90°。

## 数值验收

| 外部参考 | 实际验证范围 | 最大绝对误差 | 结果 |
| --- | --- | ---: | ---: |
| ITU 验证例 rev 5.1，P.676-12 斜路径 | ITU-Rpy 维护者归档的 64 条官方输入与期望值；与业务场景使用相同的柱积分水汽分支 | 6.20×10⁻¹⁰ dB | 64/64 |
| ITU 官方 rev 8.3.0 工作簿，P.676-13 SpAtt | 1 至 350 GHz 每个整数频点的氧气、水汽、合计比衰减，各 350 个数值 | 5.33×10⁻¹⁴ dB/km | 1050/1050 |

两组检查分别固定 10⁻⁷ dB 和 10⁻⁷ dB/km 为绝对容差。第二组直接读取官方 XLSX 中的缓存参考值；计算端仍使用 P.676-12，该跨版本结果仅适用于表中注明的共同物理量。rev 5.1 的历史 ITU 工作簿旧网址返回 404，斜路径验证使用固定提交中的 CSV 转录。其 T 列为绝对温度 K；该转录表单位行的温度标签有误，实际输入量级为约 280–300 K。完整计算值以及输入文件 SHA-256 均有留存。[ITU 官方数据入口](https://www.itu.int/en/ITU-R/study-groups/rsg3/rwp3m/Pages/digprod.aspx) · [P.676-12 验例转录](https://github.com/inigodelportillo/ITU-Rpy/blob/094abb618c2a7a8cc145e93940f4571650bc2cf5/test/test_data/676/ITURP676-12_A_gas.csv) · [验证结果](evidence/summary.json)

从仓库根运行以下命令。下载阶段固定参考文件指纹，实际计算在关闭外网的容器内完成。

```sh
docker build -t chistarlink-repair:phase1 tasks/repair
docker build -t chistarlink-itur:phase2 phase2/propagation
python3 phase2/propagation/validate.py
```
