# 轨道窗口交叉校验

固定第一阶段合成 TLE，在历元后 24 小时内计算四个站点的 10° 仰角穿越。Skyfield 的 find_events 与 Orekit 的 ElevationDetector 各自判定升起和落下，逐站对齐事件数量、方向及相对历元时间。两种实现共用轨道模型和输入，这项实验检查时间、参考系和事件处理的一致性。门限为 2 秒。

在独立 Python 3.10 环境中执行：

```sh
python -m pip install orekit-jpype==13.1.4.0 jdk4py==21.0.8.0 skyfield==1.54 sgp4==2.27
python phase2/geometry/windows.py > /tmp/chistarlink-windows.json
```

首次运行需要下载固定版本的 Orekit 地球定向和闰秒数据。脚本验证文件 SHA-256 后使用本地缓存。[轨道输入](../../tasks/design/tasks.json) · [实测结果](results.json) · [Orekit 升降事件](https://test.orekit.org/site-orekit-13.1.2/apidocs/org/orekit/propagation/events/ElevationDetector.html)
