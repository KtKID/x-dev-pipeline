# Record 与状态语义

## 追加日志

状态目录包含 `events.log`。每条已提交记录占一行 UTF-8 JSON，行尾为 `\n`。字段为：

```json
{"crc32":"8位小写十六进制","expected_version":0,"key":"alpha","op":"put","request_id":"r-1","seq":1,"value":"A"}
```

`delete` 的 `value` 为 `null`。CRC 输入是移除 `crc32` 后的 object，按 `sort_keys=True`、`separators=(",", ":")`、UTF-8 编码的 JSON 字节；计算 `zlib.crc32` 并格式化为 8 位小写十六进制。

`seq` 是全局严格递增正整数。key 的当前 version 等于最近一次 put/delete 的 seq。不存在或已删除 key 的业务值均视为不存在；已删除 key 的 version 继续参与乐观版本校验。

每次新增记录必须在持有独占锁时 append、flush、fsync，然后才能返回成功。

## 写入状态机

- `put`：创建或更新字符串值。
- `delete`：写 tombstone；目标从未出现时返回 `NOT_FOUND`。
- `expected_version` 必填。key 从未出现时为 0；其余情况使用最近 mutation 的 seq，包括 tombstone。
- 版本不匹配返回 `VERSION_CONFLICT`，不得写日志。
- `request_id` 在整个 state-dir 内唯一。
- 同一 request_id 与完全相同的 op/key/value/expected_version 重试，返回首次提交的原始结果，不追加记录。
- 同一 request_id 携带不同请求内容，返回 `IDEMPOTENCY_CONFLICT`，不得写日志。

