# Fixture

`backend/` 是唯一实现范围。初始文件仅提供模块入口和 TODO，允许重写。

评测器会复制 backend 到临时目录，以新的 state-dir 执行真实 CLI 子进程、损坏注入、重启、压缩和并发测试。

