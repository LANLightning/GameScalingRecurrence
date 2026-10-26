# 最新验证桥

使用仓库根目录 reproduce.ps1 调用，自动生成本机配置；不要复制旧 runtime、origin、command 或 PID。

run_pure_task.py 默认两端各 300 秒、history=5、固定目标，所有动作来自 GameScaling。新机器生成自己的起点与水源参考；数据用于观察，不作为模型输入。

Java 21 + ASM 9.8 可通过 build_bridge.py 重建并运行 VerifyRestoreTest。预编译 craft-bridge-5min.jar 与本次五分钟实机桥一致。

只支持 Minecraft 1.21.1 / NeoForge 21.1.265 单人世界。若 Attach 被拒绝，请从与游戏相同桌面用户/权限的终端执行，不能据服务健康接口宣称游戏控制已成功。完整卸载后再次测试须重新启动 Minecraft JVM。
