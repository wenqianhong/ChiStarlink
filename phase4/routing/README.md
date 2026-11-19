# 从工程规格搭建星座故障期间的业务转发系统

**来源**为 EasySatSim Case 3，固定提交 `aa738929bc5fa6c41217f96b8a1c6fac35ee802b`。官方给出了实验规格、协议栈扩展点、可执行参考工程、原始收发事件以及十个配对种子的汇总结果。[原始实验](https://github.com/imust-lezhang/EasySatSim/tree/aa738929bc5fa6c41217f96b8a1c6fac35ee802b/cases/case3)

## 工程题干

在上游提供的通用 EasySatSim 仿真内核上，从规格搭建一套独立场景。配置 16 个轨道面、每面 25 星的 1,150 km Walker 星座，倾角为 53°。将 200 个用户按给定地理分布和种子分为两组，形成 100 对双向应用流。自第 5 秒开始按源业务计划发送 1,200 字节报文，保留消息标识以及逐跳路径。第 105 秒永久停用 377 号卫星，持续观测到第 200 秒。

交付两套可运行的路由策略。集中式控制每 50 秒发布一版全局路由表，各跳转发要核对缓存条目的表版本，重新计算过期下一跳。分布式转发使用邻接状态及已访问路径绕过失效下一跳。两套策略使用同一套用户坐标、业务生成器、物理链路模型与故障时钟。[路由与事件规格](https://github.com/imust-lezhang/EasySatSim/blob/aa738929bc5fa6c41217f96b8a1c6fac35ee802b/cases/case3/TUTORIAL.md)

| 模块 | 验收依据 |
|---|---|
| 场景与接入 | 检查 400 颗运动卫星、200 个终端、100 对双向流，以及同种子下两模式的用户部署。 |
| 星间与星地链路 | 沿用场景的可见性、动态速率、多普勒损耗与链路预算。官方采用系统级 PHY 近似。 |
| 控制面 | 确认故障事件、集中式更新时刻、失效前后两种路由状态。验证本地绕路只使用当时可用的邻居与路径记录。 |
| 协议栈与业务 | 保留发包 ID、收包 ID 和跳数。以发包时刻分组，跨边界到达的包归于原发包窗口。 |
| 端到端 | 分别报告 [0,105)、[105,150)、[150,200) 秒的交付率与平均跳数。须同时解释正常阶段、故障窗口与刷新后恢复。 |

## 原生重放

从 ChiStarlink 仓库根目录执行。使用独立的空输出目录挂载覆盖作者自带结果。容器以只读方式加载上游，两个模式各有独立共享内存。

```sh
git clone https://github.com/imust-lezhang/EasySatSim.git /tmp/easysat-src
git -C /tmp/easysat-src checkout --detach aa738929bc5fa6c41217f96b8a1c6fac35ee802b
docker build --platform linux/amd64 -t chistarlink/easysat-case3:aa73892 -f phase4/routing/Dockerfile /tmp/easysat-src
for mode in centralized distributed; do
  out=$(mktemp -d "/tmp/easysat-${mode}.XXXXXX")
  docker run --platform linux/amd64 --rm --network none --shm-size=1g \
    -e NUMBA_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=1 -e PYTHONHASHSEED=20260811 \
    -v /tmp/easysat-src:/src:ro -v "$out":/src/cases/case3/experiment/output \
    chistarlink/easysat-case3:aa73892 python cases/case3/main.py \
    --routing-mode "$mode" --seed 20260811 --headless
  python3 phase4/routing/score.py "$out"/case3_events_*.csv
done
```

上游控制器使用墙钟定时器终止运行。复核时需要检查原始事件是否覆盖故障和刷新窗口，进程退出码本身不能证明实验成功。作者发布的十组配对种子可用于对照评测口径。模型能力测评还需要隔离参考源码，向被测模型仅提供规格、内核和接口，并用独立种子验证提交。

## 给被测模型的起点

`python3 phase4/routing/pack_starter.py /tmp/easysat-src /tmp/easysat-starter.zip` 从固定 Git 对象导出通用内核、资源、许可证、两个输入规格文件和中文题干。分发这个 ZIP 时，参考路由实现、预计算路由表、作者的结果和 Git 历史都位于包外。[单独查看题干](SPEC.md)

在本机运行上游默认的 200 秒墙钟后，两种模式的模拟时间约到 192.6 秒。为覆盖末段，我们另将 `simulation_config.py` 中唯一的墙钟终止参数 `CASE_RUNNING_TIME_REAL_SECONDS` 设置为 235 秒并重复两种运行。轨道、业务、控制策略和模拟采样均保持原配置；评分器按模拟时间裁切到 [0,200) 秒。将改过这一行的文件额外挂载到容器内同名路径即可复验。四次运行的原始事件和本批同种子对照保存在 evidence/。
