
# 本次修复与快速复现

修复范围是 GameScaling 客户端采样契约和 Minecraft 桥，不是重新量化模型，也没有更换 NInfer 推理内核。

## 空动作定位

原客户端只发送 temperature=1，遗漏 top_p、top_k、惩罚参数。当前 NInfer 融合基线的 Qwen 非思考默认值为 top_k=20、top_p=0.8、presence_penalty=1.5；llama.cpp 适配器则使用 top_k=0、top_p=1、无惩罚。两端的请求表面同温度，实际采样不一致。

修复：streaming_policy.py 显式发送 temperature=1、top_k=20、top_p=1、min_p=0、presence_penalty=0、frequency_penalty=0，并记录逐请求种子。native_protocol.py 透传种子与惩罚参数；旧适配器会丢弃请求中的 seed。选 top_k=20 是因为当前 NInfer 构建只支持最多 20 个候选，同时将 llama.cpp 对齐到 20；不宣称与上游 vLLM 的无限 top-k 完全相同。

同一截图、相同 5 轮空动作历史、显式 seed 0–7：原 NInfer 默认配置 8/8 空动作；对齐参数后 6/8 空动作。另一次修复后固定截图 12 轮连续回放，10 轮非空，包含 W 前进。空动作历史会继续强化停住，两端都可能出现；修复没有删除历史、拒绝空动作、强制 W 或补发子目标。不能据此宣称所有后端数值差异或模型能力问题已解决。

## VerifyError 定位

真实 InputConstants.isKeyDown 字节码中，偏移 13 的 StackMapTable 为 frame_type=249（CHOP），错误地移除了 long/int 局部变量，后续旧补丁仍执行 iload_2，造成校验失败；旧 v4 的虚拟键序列也留在重新转换的输入中。

InputKeyTransform 精确剥离本项目 v3/v4/v5 的虚拟键序列，安装时只注入一份，卸载时不注入；两种路径均以游戏类加载器计算 COMPUTE_FRAMES | COMPUTE_MAXS。恢复后该方法只查询 GLFW，帧类型为 SAME，已无 gamescaling 虚拟键查询。失败也会释放键、停止观察循环、移除变换器并写入明确失败状态，不能伪报恢复成功。

新增启动防重放：重载时记住现有 command.properties 的 ID，避免重新执行旧 action/shutdown。已通过 -Xverify:all 回归测试，复现缺失帧和真实 CHOP 错误；并在 NeoForge 内验证卸载、状态文件停止更新及再次挂载。

## 在另一台机器复现

前提：按 GameScaling-快速复现.md 部署好两个模型服务；Windows、JDK 21、Minecraft 1.21.1 / NeoForge 21.1.265、Python requests/Pillow/Jinja2、FFmpeg。模型权重和完整引擎不在本补丁包内。

1. 将 gamescaling-sampling-fix 中的 streaming_policy.py、native_protocol.py 放入部署目录 tools/；先备份原文件。重启 llama.cpp 适配器，让新 native_protocol 生效；无需重编 NInfer。同时复制两个 test_*.py 文件到 tools/，运行部署目录内的 tools/test_stream_protocol.py 与 tools/test_sampling_contract.py。
2. 启动新的 Minecraft JVM 并进入单人测试世界。将 craft-task-bridge-fixed 整个目录放到可写位置，用 configure_bridge.py --game-dir "实际游戏目录" --pid 游戏Java进程PID 更新配置。START_BRIDGE.bat 中的 WATER_JAVA 应指向 JDK 21 java.exe。
3. 在 reload.properties 写三行：id=新的唯一标识、op=load、jar=craft-implementation-fixed-r5.jar。双击 START_BRIDGE.bat；核对 bootstrap-status.txt 为 Implementation attached、实时 snapshot 的 error 为空且 ready=true。初始只观察。
4. python bridge_client.py origin 记录新机器自己的起点；python survey_water.py --world "世界存档目录" 建立观察用水体参考。不要直接复制旧 runtime 中的命令或坐标当作自己的基线。
5. 检查 run_pure_task.py 的模型端口和 FFmpeg 路径。本次 NInfer 为 8095；llama.cpp 原生 8093，新适配器验证端口为 8096。脚本发布默认使用 8094；复现本次验证端口可传 --llama-url http://127.0.0.1:8096/v1。两端显式采样参数相同，seed_base=20261026，每次递增；不同实现不保证同种子输出相同。
6. python run_pure_task.py --root "部署目录"。保持游戏前台。默认各端上限 300 次决策或 300 秒有效时间。模型自己打开暂停菜单会使该轮提前结束；停止原因必须保留。结束后一端尚未执行时，可在实验间复位，再用 --backend llama --resume-directory "原试验目录" 补完另一端，不能覆盖已有后端结果。
7. 控制器结束后先 reset(origin) 恢复实验基线，再 python bridge_client.py shutdown。检查 runtime/status.json 中 class_restored、observer_stopped、transformer_removed、keys_released 全为 true，且 snapshot 修改时间不再变化。也可用 shutdown_bridge.py 自动核对并停止 bootstrap。下一次全新安装建议从新游戏 JVM 开始。
8. python make_comparison_video.py "试验目录" 生成完整时长并排录像；短轮结束后为黑屏文字提示，不伪装成持续游戏。原片、逐步输出、坐标和参数日志均保留。

源代码只适配上述 Minecraft 版本，不是通用 UI 树或全游戏插件。两轮仅复位玩家/物品/昼夜状态，不回滚全世界的方块与实体；随机轨迹也不保证跨机器一致。测试报告会分别说明接口修复与任务成功率。

## 复测期间补充修复

- 命令已提交后，遇到快照超过 2 秒未更新，在原有 5 秒回执期限内等待恢复；不会重发动作，也不以旧快照提交新动作。一次创造栏交互出现约 2.2 秒游戏卡顿，原片作为中断记录保留，之后重跑该后端。
- 异常记录即使拿不到新快照，也保存最后已知状态，并明确标注不是新鲜状态；请求执行前另存 pending-action，防止丢失未获回执的模型输出。
- 实验间 reset 同时恢复客户端鼠标携带物与 2×2 合成格；位置、朝向、背包、携带物、合成格、选中槽和模式全部通过后才启动下一轮。
- 当前验证实现为 craft-implementation-fixed-r5.jar。输入执行与卸载修复不变，r5 还完整恢复飞行状态。build_bridge.py 可用本机 JDK 21 与 ASM 9.8 重建并自动运行 JVM 回归测试。
