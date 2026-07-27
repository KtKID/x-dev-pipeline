# Journal Index Recovery

实现一个仅依赖 Python 标准库的本地键值日志。它由命令行驱动，所有状态保存在调用者指定的目录，支持进程重启、幂等请求、乐观版本、删除、尾部恢复、原子压缩和多进程写入。

实现目录：`fixture/backend/`。

公开入口：

```bash
python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]
```

模块边界至少包含：

- `record.py`：规范化 record、CRC-32 编解码与损坏分类。
- `store.py`：snapshot + log 重放、状态机、幂等、版本与压缩。
- `locking.py`：跨进程读写锁。
- `cli.py`：参数、JSON 输出与稳定退出码。

所有命令只向 stdout 输出一个 JSON object。stderr 可用于诊断。不得依赖数据库、守护进程、网络或第三方包。

