# MATLAB NTN 容器

基于 MathWorks 官方 R2025b Linux amd64 镜像，使用 MATLAB Package Manager 安装 5G Toolbox 和 Satellite Communications Toolbox。包管理器会同时安装 Communications Toolbox、DSP System Toolbox 和 Signal Processing Toolbox。

在仓库根目录构建镜像并打开本机浏览器入口：

```sh
docker build --platform linux/amd64 -t chistarlink/matlab-ntn:r2025b containers/matlab-ntn
docker run --init -it --rm --platform linux/amd64 --shm-size=512m \
  -p 127.0.0.1:18888:8888 chistarlink/matlab-ntn:r2025b -browser
```

访问 <http://127.0.0.1:18888>，使用已关联相关产品许可的 MathWorks 账号登录。具有网络许可的环境也可从宿主机传入预先配置的 `MLM_LICENSE_FILE`。在启动的 MATLAB 会话内执行 `ver` 检查产品列表，并实际运行目标工程确认工具箱可用性。

Apple Silicon 主机使用 amd64 仿真运行 Linux 镜像。MathWorks 将此组合列为未经认证的配置。[容器许可和运行方式](https://www.mathworks.com/help/cloudcenter/ug/matlab-container-on-docker-hub.html) · [Apple Silicon 支持说明](https://www.mathworks.com/matlabcentral/answers/2183171-can-i-run-matlab-in-docker-container-on-macos-with-an-apple-silicon-arm-processor)
