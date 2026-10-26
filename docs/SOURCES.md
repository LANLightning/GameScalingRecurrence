# 技术来源与外部 URL

本清单列出复现使用的直接来源、构建与验证工具、依赖入口和参考文档。用途分别标注；“参考”不表示已部署或实测该后端。

## NInfer 技术来源

| 仓库 | 在本项目中的用途 |
|---|---|
| [Neroued/ninfer](https://github.com/Neroued/ninfer) | 原始推理引擎与模型格式上游 |
| [1314521gjy/ninfer-fusion-kvmem](https://github.com/1314521gjy/ninfer-fusion-kvmem) | 融合实现、KVMem、主机 KV、ring 与复用能力的基础 |
| [ByronLeeeee/ninfer-extended](https://github.com/ByronLeeeee/ninfer-extended) | 小模型形状、算子和前端实现参考 |

融合上游记录提交为 [4e93bb8ab89b583653a9d16235582c688226ff05](https://github.com/1314521gjy/ninfer-fusion-kvmem/commit/4e93bb8ab89b583653a9d16235582c688226ff05)，在此基础上叠加适配改动；不是直接使用最新 main。小模型补丁与数值测试在 `patches/ninfer-small/`。extended 参考未记录独立固定提交，因此不把它的最新版本当作此次构建版本。

## 已锁定的主要版本

| 对象 | 版本／修订 |
|---|---|
| GameScaling 客户端 | f5a05714892307c3e3aefbf6cc2b177e90798a54 |
| GameScaling-0.8B-S3 权重 | 1b89640dcf2ef51fb53ad9338a0725e9622dd200 |
| llama.cpp 转换器源码 | v0.7.0 |
| llama.cpp Windows Vulkan 服务二进制 | b11669；与转换器源码版本分开记录 |
| FFmpeg 录像工具 | 7.1 essentials，附带 README 指定提交 b08d7969c5 |
| ASM | 9.8 |
| 游戏／Java | Minecraft 1.21.1，NeoForge 21.1.265，Java 21 |
| Python | 验证版本 3.14.3；包版本见 requirements-runtime-lock.txt |
| GitHub CLI | 2.103.2，仅用于发布 |

本项目发行文件以 `release-assets.json`、`runtime-files.json` 的 SHA-256 为准。BF16/Q8_0 模型文件由已锁定检查点转换；两套格式的区别见 [PRECISION.md](PRECISION.md)。

## 来源、依赖与参考文档

| 名称 | URL | 用途 |
|---|---|---|
| NInfer | [链接](https://github.com/Neroued/ninfer) | 推理引擎上游 |
| NInfer fusion + KVMem | [链接](https://github.com/1314521gjy/ninfer-fusion-kvmem) | 融合实现与 KVMem 基线 |
| Fusion pinned commit | [链接](https://github.com/1314521gjy/ninfer-fusion-kvmem/commit/4e93bb8ab89b583653a9d16235582c688226ff05) | 记录的融合上游提交 |
| NInfer extended | [链接](https://github.com/ByronLeeeee/ninfer-extended) | 小模型算子及前端实现参考；具体变更见 patches/ninfer-small |
| GameScaling project | [链接](https://gamescaling.github.io/) | 论文项目介绍 |
| GameScaling GitHub | [链接](https://github.com/THUSI-Lab/GameScaling) | 官方项目源码与运行流程 |
| GameScaling client | [链接](https://huggingface.co/THUSI-Lab/GameScaling) | 客户端与动作协议 |
| GameScaling 0.8B S3 | [链接](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3) | 本次转换与运行的模型 |
| Paper on Hugging Face | [链接](https://huggingface.co/papers/2610.28698) | 论文入口 |
| Paper HTML | [链接](https://arxiv.org/html/2610.28698v1) | 论文原文参考 |
| Qwen3.5 0.8B | [链接](https://huggingface.co/Qwen/Qwen3.5-0.8B) | 模型卡列出的基础架构；不是本次直接运行的权重 |
| llama.cpp | [链接](https://github.com/ggml-org/llama.cpp) | GGUF 转换与推理项目 |
| llama.cpp converter source | [链接](https://github.com/ggml-org/llama.cpp/tree/v0.7.0) | 使用的转换器源码版本 |
| llama.cpp Vulkan runtime | [链接](https://github.com/ggml-org/llama.cpp/releases/tag/b11669) | 使用的 Windows Vulkan 二进制版本 |
| llama.cpp Vulkan x64 archive | [链接](https://github.com/ggml-org/llama.cpp/releases/download/b11669/llama-b11669-bin-win-vulkan-x64.zip) | 稳定下载地址 |
| FFmpeg recording build | [链接](https://www.gyan.dev/ffmpeg/builds/) | 录像／拼接工具发行来源 |
| FFmpeg recording source | [链接](https://github.com/FFmpeg/FFmpeg/commit/b08d7969c5) | 录像工具附带 README 指定的源码提交 |
| FFmpeg | [链接](https://github.com/FFmpeg/FFmpeg) | 媒体编解码库源码项目；运行库具体文件见 runtime-files.json |
| ASM | [链接](https://asm.ow2.io/) | Java 字节码变换与栈帧重算 |
| ASM Maven artifact | [链接](https://repo.maven.apache.org/maven2/org/ow2/asm/asm/9.8/asm-9.8.jar) | 标准依赖发行入口；用于重建桥 |
| Java 21 | [链接](https://openjdk.org/projects/jdk/21/) | 游戏／桥接所需 Java 版本与标准项目 |
| Java Attach API | [链接](https://docs.oracle.com/en/java/javase/21/docs/api/jdk.attach/com/sun/tools/attach/VirtualMachine.html) | 代理加载 API 文档 |
| Java Instrumentation | [链接](https://docs.oracle.com/en/java/javase/21/docs/api/java.instrument/java/lang/instrument/Instrumentation.html) | 类重转换 API 文档 |
| JVMTI | [链接](https://docs.oracle.com/en/java/javase/21/docs/specs/jvmti.html) | 运行时能力分析参考 |
| NeoForge events | [链接](https://docs.neoforged.net/docs/1.21.1/concepts/events/) | 游戏事件与版本参考 |
| NeoForge 21.1.265 | [链接](https://maven.neoforged.net/releases/net/neoforged/neoforge/21.1.265/) | 测试目标版本的官方发行入口 |
| Minecraft Java | [链接](https://www.minecraft.net/en-us/store/minecraft-java-bedrock-edition-pc) | 测试游戏来源；不随复现包分发 |
| CUDA | [链接](https://developer.nvidia.com/cuda-toolkit) | NInfer CUDA 运行／构建依赖 |
| MSVC Build Tools | [链接](https://visualstudio.microsoft.com/visual-cpp-build-tools/) | Windows 原生引擎构建工具 |
| vcpkg | [链接](https://github.com/microsoft/vcpkg) | 原生第三方库构建来源 |
| curl | [链接](https://github.com/curl/curl) | 运行库 HTTP 依赖 |
| zlib | [链接](https://github.com/madler/zlib) | 运行库压缩依赖 |
| cpp-httplib | [链接](https://github.com/yhirose/cpp-httplib) | NInfer 第三方代码来源；由上游依赖清单管理 |
| nlohmann/json | [链接](https://github.com/nlohmann/json) | NInfer 第三方代码来源；由上游依赖清单管理 |
| spdlog | [链接](https://github.com/gabime/spdlog) | NInfer 第三方代码来源；由上游依赖清单管理 |
| utf8proc | [链接](https://github.com/JuliaStrings/utf8proc) | NInfer 第三方代码来源；由上游依赖清单管理 |
| llama.cpp Jinja | [链接](https://github.com/ggml-org/llama.cpp/tree/master/common) | NInfer 随附 llama-jinja 的上游来源 |
| Python | [链接](https://www.python.org/downloads/) | 复现脚本解释器；验证版本 3.14.3 |
| PyPI | [链接](https://pypi.org/) | Python 依赖发行源；版本由 requirements-runtime-lock.txt 固定 |
| certifi | [链接](https://pypi.org/project/certifi/2026.10.23/) | 运行时 Python 依赖 |
| charset-normalizer | [链接](https://pypi.org/project/charset-normalizer/3.5.2/) | 运行时 Python 依赖 |
| idna | [链接](https://pypi.org/project/idna/3.20/) | 运行时 Python 依赖 |
| Jinja2 | [链接](https://pypi.org/project/Jinja2/3.1.6/) | 运行时 Python 依赖 |
| MarkupSafe | [链接](https://pypi.org/project/MarkupSafe/3.0.4/) | 运行时 Python 依赖 |
| pillow | [链接](https://pypi.org/project/pillow/13.0.0/) | 运行时 Python 依赖 |
| requests | [链接](https://pypi.org/project/requests/2.34.2/) | 运行时 Python 依赖 |
| urllib3 | [链接](https://pypi.org/project/urllib3/2.8.0/) | 运行时 Python 依赖 |
| PyTorch | [链接](https://pytorch.org/) | 模型转换阶段使用；预编译运行包不要求安装 |
| Transformers | [链接](https://github.com/huggingface/transformers) | 模型配置、分词／模板一致性参考及转换工具依赖 |
| safetensors | [链接](https://github.com/huggingface/safetensors) | 原始权重格式与转换工具依赖 |
| NumPy | [链接](https://numpy.org/) | GGUF 张量目录审计与转换工具依赖 |
| Git | [链接](https://git-scm.com/) | 代码获取与版本管理 |
| GitHub CLI | [链接](https://github.com/cli/cli/releases/tag/v2.103.2) | 发布工具；不参与模型推理 |
| GitHub REST releases | [链接](https://docs.github.com/en/rest/releases/releases) | 发行发布与核验 API 文档 |
| vLLM installation | [链接](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/) | 仅作原始平台分析参考；本次未实测 vLLM |
| GameScaling 27B config | [链接](https://huggingface.co/THUSI-Lab/GameScaling-27B-S3/blob/main/config.json) | 仅作模型结构对照；本次未部署 27B |

## 固定客户端与模型文件

- [GameScaling/LICENSE](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/LICENSE)
- [GameScaling/README.md](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/README.md)
- [GameScaling/config.json](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/config.json)
- [GameScaling/examples/doom_battle1.jpg](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/examples/doom_battle1.jpg)
- [GameScaling/examples/doom_battle1_action.txt](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/examples/doom_battle1_action.txt)
- [GameScaling/examples/run_example.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/examples/run_example.py)
- [GameScaling/gamescaling/__init__.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/gamescaling/__init__.py)
- [GameScaling/gamescaling/action.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/gamescaling/action.py)
- [GameScaling/gamescaling/keymaps.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/gamescaling/keymaps.py)
- [GameScaling/gamescaling/policy.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/gamescaling/policy.py)
- [GameScaling/gamescaling/prompt.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/gamescaling/prompt.py)
- [GameScaling/prompts/example_doom_battle1.txt](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/prompts/example_doom_battle1.txt)
- [GameScaling/prompts/system_prompt_template.txt](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/prompts/system_prompt_template.txt)
- [GameScaling/requirements.txt](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/requirements.txt)
- [GameScaling/scripts/serve_vllm.sh](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/scripts/serve_vllm.sh)
- [GameScaling/tests/test_core.py](https://huggingface.co/THUSI-Lab/GameScaling/resolve/f5a05714892307c3e3aefbf6cc2b177e90798a54/tests/test_core.py)
- [GameScaling-0.8B-S3/LICENSE](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/LICENSE)
- [GameScaling-0.8B-S3/README.md](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/README.md)
- [GameScaling-0.8B-S3/chat_template.jinja](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/chat_template.jinja)
- [GameScaling-0.8B-S3/config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/config.json)
- [GameScaling-0.8B-S3/generation_config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/generation_config.json)
- [GameScaling-0.8B-S3/model.safetensors](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/model.safetensors)
- [GameScaling-0.8B-S3/preprocessor_config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/preprocessor_config.json)
- [GameScaling-0.8B-S3/processor_config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/processor_config.json)
- [GameScaling-0.8B-S3/tokenizer.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/tokenizer.json)
- [GameScaling-0.8B-S3/tokenizer_config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/tokenizer_config.json)
- [GameScaling-0.8B-S3/video_preprocessor_config.json](https://huggingface.co/THUSI-Lab/GameScaling-0.8B-S3/resolve/1b89640dcf2ef51fb53ad9338a0725e9622dd200/video_preprocessor_config.json)

## 本项目复现与录像下载

- [runtime-win-sm89.zip](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/runtime-win-sm89.zip)
- [model-ninfer-bf16.zip](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/model-ninfer-bf16.zip)
- [model-llama-q8.zip](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/model-llama-q8.zip)
- [recording-tools.zip](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/recording-tools.zip)
- [verification-evidence.zip](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/verification-evidence.zip)
- [comparison-5min.mp4](https://github.com/LANLightning/GameScalingRecurrence/releases/download/v2026.10.26/comparison-5min.mp4)

机器可读清单：[external-urls.json](external-urls.json)。
