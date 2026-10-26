# 来源与第三方许可

本仓库新增的复现脚本和桥接源码采用 Apache-2.0，见 LICENSE。保留上游文件原有许可、作者声明与限制。

- GameScaling 模型与客户端： https://huggingface.co/THUSI-Lab/GameScaling 、 https://github.com/THUSI-Lab/GameScaling 。本地模型卡标明 Apache-2.0；模型卡、配置、模板、LICENSE 保留于 models/GameScaling-0.8B-S3，客户端 LICENSE 在 client/。Release 的 BF16 .ninfer、Q8 GGUF 和 F16 mmproj 为本次转换产物，不是上游原始 safetensors。
- NInfer： https://github.com/Neroued/ninfer 、融合基线 https://github.com/1314521gjy/ninfer-fusion-kvmem 、扩展实现 https://github.com/ByronLeeeee/ninfer-extended 。Apache-2.0，许可与修改源码保留于 patches/ninfer-small。数值验证和引擎哈希见 evidence/ninfer-build-manifest.json。build_patch.py 原为特定 MSVC/CUDA 构建目录的增量链接工具，不能独立从干净环境构建；不要把它作为已验证的跨机器源码构建步骤。
- llama.cpp： https://github.com/ggml-org/llama.cpp ，MIT。Release 保留运行库，另含 LLVM OpenMP 的原许可。运行二进制逐文件 SHA-256 是此次发行身份，不用 latest 替换已验证产物。
- ASM 9.8： https://asm.ow2.io/ ，BSD 风格许可，见 bridge/ASM-LICENSE.txt 和 JAR 中 META-INF/ASM-LICENSE.txt。
- FFmpeg 7.1 essentials： https://www.gyan.dev/ffmpeg/builds/ ，本发行携带原 LICENSE 与 README.txt；该构建 GPLv3。构建来源指定 https://github.com/FFmpeg/FFmpeg/commit/b08d7969c5 ，原 README 包含构建配置。FFmpeg 为独立进程，仅负责录像与拼接。
- CUDA 13、cuBLAS、Microsoft VC Runtime：对应 NVIDIA / Microsoft 运行库条款，不适用本仓库的 Apache 许可证。它们是随原引擎取得的运行时依赖；不含驱动或 CUDA 编译工具链。

Minecraft/NeoForge、Java、显卡驱动由使用者自行安装。
