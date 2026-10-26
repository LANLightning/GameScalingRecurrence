
> 最新修复与实测见 [GameScaling-修复后实机对比](GameScaling-修复后实机对比.md) 和 [修复复现说明](GameScaling-空动作与卸载修复说明.md)。下文保留此前测试的历史状态。

# GameScaling：快速复现

> 2026-10-26；Windows x64 / RTX 4070 Laptop 8 GB / sm89。**后续已通过游戏桥完成双后端动作实测；完整水源/取物/合成任务未成功。详见 GameScaling-完整任务实测.md。以下旧测试记录保留原时点结论。** 这份文档复现的是已验证的部署，不把它称为“已能自动玩 Minecraft”。

## 1. 复制什么

推荐复用已编译产物。新机器准备 Python **3.14 x64**（本机 3.14.3）与可用的 NVIDIA 驱动，`nvidia-smi` 能正常运行。当前 NInfer 二进制只按 **sm89 / BF16** 验证；其他 GPU 架构需要重新编译，不能保证直接运行。

把下列文件从本机 `${DEPLOY_ROOT}` 复制到新机器任意目录，并保持相对结构；再将附带的 `GameScaling-复现辅助包.zip` 解压到该目录：

```text
GameScaling/
├─ ninfer-small/ninfer-serve-small.exe
├─ engine/*.dll                         # 全部运行库，不必复制旧 exe
├─ llama-runtime/                       # 整个目录，包括 exe 和 DLL
├─ models/ninfer/gamescaling-0.8b-s3-bf16.ninfer
├─ models/gguf/GameScaling-0.8B-S3-Q8_0.gguf
├─ models/gguf/mmproj-GameScaling-0.8B-S3-F16.gguf
└─ models/GameScaling-0.8B-S3/chat_template.jinja
```

辅助包提供 `client/`、`tools/`、启动批处理、提示词、依赖锁定文件和哈希清单，**不含上面的大文件**。不要复制旧 `.venv`、`python-env`、`runtime-env`；不要复制 `data/*session.json` 中的旧进程记录。仅运行模型无需安装 PyTorch、MSVC 或完整 CUDA Toolkit，也无需复制原始 safetensors。

## 2. 安装与启动

在部署目录打开终端：

```bat
SETUP_RUNTIME.bat
RUN_RUNTIME.bat tools\verify_runtime.py --hash
```

安装器在本目录建立独立 `runtime-env`，不使用全局 site-packages；依赖版本固定在 `requirements-runtime-lock.txt`。需要网络下载依赖。哈希检查失败时先修正复制文件，不要继续测速度。

分别在两个终端运行，并保持窗口开启：

```bat
START_NINFER.bat
START_LLAMA.bat
```

| 后端 | 对外接口 | 加载成功判断 |
|---|---|---|
| NInfer BF16 | `http://127.0.0.1:8095/v1` | `/models` 返回 `gamescaling`，状态 `loaded` |
| llama.cpp Q8 | `http://127.0.0.1:8094/v1` | 原生 `http://127.0.0.1:8093/health` 返回 `ok` |

默认 `START.bat` 启动 NInfer。端口占用时不会杀死已有进程；先确认是不是已启动。`STOP.bat` 只终止创建时间和路径均匹配的本项目记录进程。API 监听本机回环地址。

## 3. 最短验收

```bat
RUN_RUNTIME.bat tools\streaming_policy.py --backend ninfer --base-url http://127.0.0.1:8095/v1 --trials 3 --report ninfer-smoke.json
RUN_RUNTIME.bat tools\streaming_policy.py --backend llama --base-url http://127.0.0.1:8094/v1 --trials 3 --report llama-smoke.json
RUN_RUNTIME.bat tools\benchmark_decisions.py --backend ninfer --name ninfer-new-machine
RUN_RUNTIME.bat tools\benchmark_decisions.py --backend llama --base-url http://127.0.0.1:8094/v1 --name llama-new-machine
```

检查 `reports/` 中的 `parsed/valid`、`truncated`、`wall_ms` 和 `first_action_ms`。TTFT 是首 token，**不等于**首个可用动作。若只有 `length` 或无效动作，不算验收通过。

## 4. Minecraft 实机验证

用户本轮实际打开的是 **原版 1.21.1 NeoForge**，不是最早指定的 TEST_INSTANCE Beta 目录。先进入测试世界并关闭暂停菜单；两个模型服务必须先启动。

```bat
CALIBRATE_INPUT.bat
LIVE_TEST.bat --pairs 6 --temperature 0
LIVE_TEST.bat --pairs 4 --temperature 1 --execute
```

运行后 30 秒内切回游戏。先验证固定左转/前进是否真实生效；没有反应就停在输入排查，不应继续宣称模型接管成功。`LIVE_TEST` 默认只观察；`--execute` 才执行经过筛选的移动/转向，每块 200 ms，禁用攻击和放置，鼠标幅度限为 ±30‰。F9 停止、F8 暂停，窗口失焦停止发输入。

测试器给两后端同一张截图、轮换请求顺序、关闭历史，交替选择一方动作执行。结果与前后截图保存在 `reports/minecraft-live-*/`。判定成功必须同时满足：动作解析成功、输入实际生效、目标方向正确。画面云朵变化和 `SendInput=1` 都不能单独证明成功。

## 5. 本次实机结果

| 真实 Minecraft 场景 | 每后端样本 | NInfer 中位耗时 | llama.cpp 中位耗时 | 结果 |
|---|---:|---:|---:|---|
| 安全探索，温度 0 | 6 | 448 ms | 353 ms | 全部不操作 |
| 原地向左看，温度 0 | 6 | 427 ms | 361 ms | 全部不操作 |
| 原地向左看，温度 1 | 4 | 468 ms | 400 ms | 出现动作，但方向不稳定 |

共 32 次模型请求均能解析。第三轮两后端各有 6 次鼠标输入调用返回成功，但画面未呈现对应转向；固定输入校准也未确认移动。用户另反馈普通桌面运行校准器“完全没反应”。**结论：推理链通过，输入链和任务完成未通过。** 原因尚未定位，不能直接归罪于 Raw Input、权限或模型。

耗时包含客户端编码与请求，不含截图及动作执行；双模型同时驻留显存，GPU 同时运行 Minecraft，BF16 与 Q8 的生成长度可能不同。样本很少，不代表稳定游戏帧率，也不是纯引擎公平排名。当前没有 vLLM 实测。

## 6. 参数与故障点

- NInfer：逻辑上下文 32768、设备 KV 8192、Host KV 512 MiB、prefill 128、视觉上限 512；CUDA Graph、KVMem、Host-backed reuse、ring 开启。
- `NINFER_KV_WINDOW=4096`，`NINFER_KV_RETRIEVE=2048`；`--max-shared-prefixes 0` 避开已换出 KV 的共享快照错误，仍保留会话缓存。不要直接恢复共享前缀默认值。
- 常规客户端：854×480、JPEG、历史 2；实机配对测试历史 0。Base64 只是传输格式。
- `assistant prefill not supported`：确认启用 `--assistant-prefill`，请求 `enable_thinking=false`，并使用本补丁引擎和原始模板。
- `active KV snapshot full page is not stable`：检查是否遗漏 `--max-shared-prefixes 0`。
- 不要换用旧 `gamescaling-0.8b-s3-q8.ninfer`；本轮通过的是 BF16 `.ninfer`。
- 当前 `build_patch.py` 是依赖原 fusion 构建产物的本机增量链接脚本，**不是独立跨机器编译器**。源码重建须使用同一融合基线，应用 `GameScaling-NInfer-source-patch.zip`，重新配置本机 CUDA/MSVC 和 GPU 架构，再跑数值测试；不能随意套到 GitHub 最新 main。

实现改动与待办见 `GameScaling-修改优化点.md`；实测原始证据见 `Minecraft-双后端实机证据.zip`。

## 新增：48 对实时画面测速

已追加 96 次正式请求（另 12 次预热），原始截图、请求日志与复测脚本均已保存。温度 0 完整响应中位数：NInfer 422.5 ms、llama.cpp 353.4 ms；温度 1：436.0 ms、418.5 ms。此前小样本记录仍保留，最新统计见 [Minecraft-实时配对测速报告.md](Minecraft-实时配对测速报告.md)。本次只测实时画面推理，键鼠控制问题仍未解决。

## 新增：游戏内实体桥与水源任务

已通过游戏内 API 实测转向、移动、实时 XYZ/视角读取及起点复位；旧 SendInput 链仍未修复。v3 桥完成两后端各 80 次动作，均未到达最近水源目标。实际三维路程 NInfer 127.79 格、llama.cpp 59.45 格；水平路程 57.09/19.96 格。详细数据和限制见 [水源任务-实际路径对比.md](水源任务-实际路径对比.md)。早期“输入未通过”描述保留为历史记录，不能代表此新增游戏内桥的当前状态。

