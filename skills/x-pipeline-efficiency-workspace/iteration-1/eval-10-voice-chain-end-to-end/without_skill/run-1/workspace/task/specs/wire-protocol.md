# 规范：设备-后端传输协议

TCP 长连接，二进制帧。本规范是帧格式与错误码的真源。

## 帧格式

```
+--------+--------+---------+---------+----------+--------+
| magic  | type   | seq     | len     | payload  | crc32  |
| 2 字节 | 1 字节 | 4 字节  | 4 字节  | len 字节 | 4 字节 |
+--------+--------+---------+---------+----------+--------+
```

- magic：`0xA5 0x5A`；
- 多字节整数一律大端（网络字节序）；
- crc32：对 `type + seq + len + payload` 的 CRC32（即除 magic 和 crc 本身外的全部字节）；
- 载荷上限 `MAX_PAYLOAD = 262144` 字节，声明超过此值的帧为非法帧；
- TCP 是字节流：接收方必须自行处理粘包与半包。

## 帧类型

| type | 名称 | 方向 | seq 语义 | payload |
|---|---|---|---|---|
| 0x01 | HELLO | 设备→后端 | 固定 0 | JSON：`{"device_id": str, "session_id": str}` |
| 0x02 | AUDIO_CHUNK | 设备→后端 | 块号，从 1 递增 | 音频块字节 |
| 0x03 | AUDIO_END | 设备→后端 | 总块数 | JSON：`{"total_chunks": int, "sha256": <完整文件字节的sha256十六进制>}` |
| 0x04 | ACK | 后端→设备 | 见下 | 见下 |
| 0x05 | ERROR | 后端→设备 | 关联帧的 seq，无关联时 0 | JSON：`{"code": str, "msg": str可选}` |
| 0x06 | TTS_CHUNK | 后端→设备 | 块号，从 1 递增 | 播放数据块 |
| 0x07 | TTS_END | 后端→设备 | 总块数 | 见考题③ |

## ACK 规则

- HELLO 的 ACK：seq=0，payload JSON `{"last_seq": <该会话已收到的最大块号，全新会话为 0>}`——断线续传依据；
- AUDIO_CHUNK 的 ACK：seq=块号，payload 为空；设备**可以不等 ACK 连续发送**；
- AUDIO_END 的 ACK：seq=总块数，payload JSON，至少含 `{"ok": true}`（考题②扩展该载荷）。

## 错误码

| code | 场景 |
|---|---|
| BAD_MAGIC | 魔数不符 |
| BAD_CRC | CRC 校验失败 |
| PAYLOAD_TOO_LARGE | len 声明超过 MAX_PAYLOAD |
| INTEGRITY_FAIL | AUDIO_END 的 sha256 与重组结果不符 |
| UPSTREAM_TIMEOUT | 上游服务调用超时 |
| UPSTREAM_ERROR | 上游服务返回错误 |

回 ERROR 帧后，后端关闭该连接；已收块的会话状态保留（不影响断线续传）。

## 下行（后端 → 设备）

后端在 AUDIO_END 的 ACK 发出后，主动推送 TTS_CHUNK 帧、以 TTS_END 帧结束。
其余细节见考题③。
