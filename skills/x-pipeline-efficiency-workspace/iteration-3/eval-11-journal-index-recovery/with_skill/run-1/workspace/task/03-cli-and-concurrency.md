# CLI 与并发契约

## 命令

```text
put     --key KEY --value VALUE --request-id ID --expected-version N
get     --key KEY
delete  --key KEY --request-id ID --expected-version N
list
compact
recover
```

成功输出包含 `ok: true`。put/delete 首次提交与幂等重试均返回 `seq`、`key`、`version`、`replayed`；首次为 false，重试为 true。get 返回 key、value、version。list 返回按 key 字典序排列的 live items，每项含 key、value、version。compact 返回 snapshot_seq。recover 返回 truncated_bytes。

失败输出：

```json
{"ok":false,"error":{"code":"VERSION_CONFLICT","message":"..."}}
```

稳定退出码：

| code | exit |
|---|---:|
| 参数或命令错误 | 2 |
| `NOT_FOUND` | 3 |
| `VERSION_CONFLICT` | 4 |
| `IDEMPOTENCY_CONFLICT` | 5 |
| `RECOVERY_REQUIRED` | 6 |
| `CORRUPT_LOG` | 7 |
| `CORRUPT_SNAPSHOT` | 8 |

## 并发

使用 state-dir 内的 `writer.lock` 和标准库文件锁协调进程。并发 mutation、recover、compact 串行化。多个进程写不同 key 时无丢失、seq 唯一。多个进程以相同 expected_version 更新同一 key 时只有一个提交成功，其余返回版本冲突。

