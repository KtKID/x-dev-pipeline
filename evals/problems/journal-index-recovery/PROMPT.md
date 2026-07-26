# Journal Index Recovery

实现一个仅依赖 Python 标准库的本地键值日志。系统通过命令行运行，所有状态保存在调用者指定的目录中，并支持进程重启、幂等请求、乐观版本、删除、日志恢复、原子压缩和多进程并发。

## 实现范围

实现代码位于 `fixture/backend/`。初始文件提供模块入口和 TODO，允许重写：

- `record.py`：record 规范化、CRC-32 编解码与损坏分类。
- `store.py`：snapshot 与 journal 重放、状态机、幂等、版本及压缩。
- `locking.py`：跨进程状态目录锁。
- `cli.py`：参数解析、JSON 输出与稳定退出码。

公开入口：

```bash
python3 fixture/backend/cli.py --root <state-dir> <command> [arguments]
```

运行时代码只能使用 Python 标准库、本地文件和本地进程。实现不得依赖数据库、守护进程、网络、第三方包或额外的持久化真相源。

## 存储布局

```text
<state-dir>/
  events.log
  snapshot.json
  snapshot.json.tmp   # 仅写入过程中短暂存在
  events.log.tmp      # 仅 compact 过程中短暂存在
  writer.lock
```

首次命令可以创建 state-dir、空 `events.log` 和 `writer.lock`。状态目录不得持久化数据库、pickle、缓存索引或其他未声明文件。

## Journal record

`events.log` 中每条已提交记录占一行 UTF-8 JSON，行尾为 `\n`：

```json
{"crc32":"8位小写十六进制","expected_version":0,"key":"alpha","op":"put","request_id":"r-1","seq":1,"value":"A"}
```

字段固定为 `crc32`、`expected_version`、`key`、`op`、`request_id`、`seq`、`value`。`delete` 的 `value` 为 `null`。

CRC 输入为移除 `crc32` 后的 object，使用 `sort_keys=True`、`separators=(",", ":")` 和 UTF-8 编码生成规范 JSON 字节，再计算 `zlib.crc32`，结果格式化为 8 位小写十六进制。

`seq` 是全局严格递增的正整数。key 的当前 version 等于最近一次 put/delete 的 seq。已删除 key 的 version 继续参与乐观版本校验。

新增记录必须在独占锁内完成 append、flush 和 fsync，成功返回时记录已经持久化。

## 状态与幂等语义

- `put` 创建或更新字符串值。
- `delete` 写入 tombstone；目标从未出现时返回 `NOT_FOUND`。
- `expected_version` 必填。key 从未出现时为 0；其余情况使用最近一次 mutation 的 seq，包括 tombstone。
- 版本不匹配返回 `VERSION_CONFLICT`，且不写入日志。
- `request_id` 在整个 state-dir 内唯一。
- 相同 request_id 携带完全相同的 op/key/value/expected_version 重试时，返回首次提交的原始 seq、key 和 version，设置 `replayed: true`，且不追加记录。
- 相同 request_id 携带不同请求内容时，返回 `IDEMPOTENCY_CONFLICT`，且不写入日志。
- `NOT_FOUND`、`VERSION_CONFLICT` 等未提交请求不占用 request_id。

## 启动、损坏与恢复

每次命令都从已提交的 `snapshot.json`（存在时）和 `events.log` 重建状态。

- 最后一条物理记录发生截断 UTF-8、缺少换行、JSON 解析失败、字段错误或 CRC 不匹配时，分类为可恢复尾部。普通命令返回 `RECOVERY_REQUIRED`。
- 最后一条之前的记录发生任意物理损坏时，分类为 `CORRUPT_LOG`。所有命令保持只读失败，`recover` 也拒绝改写。
- 物理完整且 CRC 正确的 record 若违反 seq、版本或状态转换约束，分类为 `CORRUPT_LOG`，包括它位于日志尾部的情况。
- `recover` 仅在可恢复尾部存在时把 `events.log` 截断到最后一个有效 record 边界并 fsync。
- 健康日志调用 `recover` 幂等成功，返回 `truncated_bytes: 0`。

遗留的 `snapshot.json.tmp` 属于未提交尝试，启动时忽略。已提交的 `snapshot.json` 若发生 JSON、字段或状态语义损坏，返回 `CORRUPT_SNAPSHOT`，不得回退到 journal 猜测状态。

## Snapshot 与 compact

`compact` 在独占锁内执行：

1. 重放当前有效状态。
2. 写入 `snapshot.json.tmp`，flush + fsync。
3. 使用 `os.replace` 发布为 `snapshot.json`，并 fsync 状态目录。
4. 通过相同的临时文件 + replace 方式把 `events.log` 替换为空文件，并 fsync 状态目录。

snapshot 必须保留：

- 全局最后 seq；
- 每个 key 的 value、tombstone 和 version；
- 全部已提交 request_id 的请求指纹与首次结果。

compact 后重启必须保持业务状态、幂等账本和 seq 单调。进程在 snapshot 发布后、旧 journal 清空前崩溃时，重启必须识别 snapshot 已包含的 journal 前缀，避免重复应用 mutation。

## CLI 契约

命令：

```text
put     --key KEY --value VALUE --request-id ID --expected-version N
get     --key KEY
delete  --key KEY --request-id ID --expected-version N
list
compact
recover
```

每次命令只向 stdout 输出一个 JSON object；stderr 可用于诊断。

成功输出：

- put/delete 首次提交与幂等重试：`ok`、`seq`、`key`、`version`、`replayed`。
- get：`ok`、`key`、`value`、`version`。
- list：`ok`、按 key 字典序排列的 live `items`；每项包含 `key`、`value`、`version`。
- compact：`ok`、`snapshot_seq`。
- recover：`ok`、`truncated_bytes`。

失败输出固定为：

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

## 并发要求

使用 state-dir 内的 `writer.lock` 和标准库文件锁协调进程。mutation、recover 和 compact 必须串行化。

- 多个进程并发写入不同 key 时，不丢失已成功提交的 mutation，且 seq 全局唯一。
- 多个进程以相同 expected_version 更新同一 key 时，只允许一个提交成功，其余返回 `VERSION_CONFLICT`。
- 并发操作结束后，journal、snapshot、幂等账本和查询结果必须保持一致。

## 交付与验证

完成 `fixture/backend/` 的实现，并提供可重复运行的验证命令。可以自行选择分析、设计、实现和测试方式。最终说明实现文件、验证命令、测试结果及仍然存在的风险。
