# 恢复与压缩

## 启动与损坏分类

每次命令都从 `snapshot.json`（存在时）和 `events.log` 重建状态。

- 最后一条物理记录出现截断 UTF-8、缺少换行、JSON 解析失败、字段错误或 CRC 不匹配，分类为可恢复尾部。普通命令返回 `RECOVERY_REQUIRED`。
- 最后一条之前的任意记录损坏，分类为 `CORRUPT_LOG`。所有命令保持只读失败，`recover` 也拒绝改写。
- `recover` 仅在可恢复尾部时，把 `events.log` 截断到最后一个有效记录边界并 fsync；健康日志调用 recover 幂等成功。

## Snapshot 与 compact

`compact` 在独占锁内：

1. 重放当前有效状态。
2. 写 `snapshot.json.tmp`，flush + fsync。
3. `os.replace` 为 `snapshot.json`，并 fsync 状态目录。
4. 以相同临时文件 + replace 方式把 `events.log` 替换为空文件，并 fsync 状态目录。

snapshot 必须保留：全局最后 seq、每个 key 的 value/tombstone/version，以及全部 request_id 的请求指纹和首次结果。compact 后重启保持状态、幂等与 seq 单调。

遗留的 `snapshot.json.tmp` 属于未提交尝试，启动时忽略。已提交 `snapshot.json` 损坏时返回 `CORRUPT_SNAPSHOT`，不得回退到日志猜测状态。

