> spec_version: 3

# voice-chain

## 任务目标

- 后端在单次 TCP 连接中完成 HELLO、音频上传、完整性校验、ASR→LLM→TTS 编排、结果落盘和 PCM 音频下发，并为每个输入帧返回规范定义的 ACK 或 ERROR。
- 后端正确处理 TCP 半包、粘包、流水线发送和进程内断线续传，上传文件与设备原始 WAV 逐字节一致。
- 多设备会话并发隔离；任一上游超时或 HTTP 错误均在有限时间内转成设备可观察的 ERROR；下行断开只终止当前连接。

## 非目标

- 不实现跨进程续传、身份认证、TLS、真实 ESP32 固件或真实云 ASR/LLM/TTS 接入。
- 不修改 `fixture/device-sim/`、`fixture/mock-services/` 与 `fixture/assets/` 测试设施。
- 不持久化会话元数据；进程重启后只保留已落盘文件，不恢复续传块状态。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/protocol.py` | 目标 | 流式解析二进制帧并携带关联 seq 报告协议错误 | 半包/粘包或伪造超长 len → 解析错位或无界等待 → 连接挂死及内存压力 | CRC 覆盖 `type+seq+len+payload`；载荷上限 262144；协议错误关闭当前连接 | `J1` |
| `fixture/backend/app.py` 上传处理 | 目标 | 保存会话块、续传 ACK、重组及校验 WAV | 流水线、重复块、乱序或同 session 并发 → 文件错序/串扰 → 完整性或隐私事故 | 会话按 session_id 隔离；只有 1..N 连续块且 sha256 相符才落盘；上传文件逐字节一致 | 用户任务 / `J2` |
| `fixture/backend/http_client.py` 与编排 | 目标 | 顺序调用三个本地 HTTP 服务，执行超时和 5xx 重试策略 | 超时、5xx、4xx、连接失败或畸形响应 → 无应答/错误结果 → 设备挂死 | ASR→LLM→TTS 严格顺序；超时不重试；5xx 最多重试配置次数；失败不发成功 ACK | 用户任务 / `J3` |
| `fixture/backend/audio.py` 与下行 | 目标 | 校验 TTS WAV 格式、提取 PCM、分块和发送完整性尾帧 | WAV 格式不受设备支持或下行中断 → 无法播放/线程异常 → 当前或其他会话受影响 | 下行仅 PCM16LE/单声道/16000Hz；ACK 先于 TTS_CHUNK；TTS_END 可校验完整 PCM；断连只影响当前连接 | 用户任务 / `J4` |
| `fixture/device-sim/` | 下游 | 消费 ACK/ERROR/TTS 帧并原样保存下行负载 | 下行字段与顺序偏离协议 → 客户端等待或错误落盘 | 启动与协议契约保持兼容，测试设施只读 | 用户任务 |
| `fixture/mock-services/` | 上游 | 提供确定性 ASR/LLM/TTS 和单次故障注入 | 重试次数或超时单位错误 → 重试不足/等待过长 | URL、毫秒超时、5xx 重试次数均取 `config.json` | 用户任务 / `J3` |
| `sessions/<session_id>/` | 下游 | 保存 `upload.wav` 与 `reply.wav` | 非法 session_id 路径穿越或部分写入 → 覆盖工作区文件/消费者读到截断内容 | session_id 只用作受控目录名；文件在校验成功后原子替换；不同会话目录隔离 | `J5` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | 线协议常量以 `wire-protocol.md` 为真源，非法魔数关联 seq 为 0，其余可解析头部的协议错误关联该帧 seq | 用户任务 / 规范 | 规范定义帧布局、MAX_PAYLOAD、错误码及“无关联时 0”；魔数错时头部不可被信任 | 已确认 |
| J2 | 块必须按 1 递增；幂等重传允许相同 seq+内容，冲突重传和 AUDIO_END 缺块均按 `INTEGRITY_FAIL` 终止 | 用户任务 / LLM 推断 | 规范定义块号从 1 递增、续传最大块号及完整性错误；这是避免错误 ACK 推进断点的最小安全规则 | 已确认 |
| J3 | `retry_max_5xx` 表示首次调用之外允许的重试次数；值 1 最多发起 2 次请求 | 用户任务 / LLM 推断 | 题面用“重试次数上限”，常规语义为 retry 次数，不含首次尝试 | 已确认 |
| J4 | TTS_CHUNK 载荷为从 TTS WAV 提取的 PCM 裸流，每块取音频规范的 3200 字节；TTS_END JSON 为 `{"total_chunks": int, "sha256": <完整PCM sha256>}` | 用户任务 / LLM 推断 | 播放器只支持 PCM16LE/单声道/16000Hz，要求可校验完整性；下行尾帧细节留白，块大小沿用规范唯一音频块大小 | 已确认 |
| J5 | session_id 限制为 1..128 个 ASCII 字母、数字、点、下划线、短横线，且禁止 `.`、`..`；device_id 必须为非空字符串 | LLM 推断 | 题面允许显式记录最小安全假设；该约束防止目录穿越并保留常见设备标识 | 已确认 |
| J6 | HELLO/END JSON、帧类型、seq、块大小或 TTS WAV 格式不合法时发送 `INTEGRITY_FAIL` | LLM 推断 | 规范未为结构/顺序错误分配独立错误码；选用现有且最接近“无法形成完整有效音频会话”的错误码，保持错误码真源封闭 | 已确认 |
| J7 | 同一 session 完成后的重连复用缓存的编排结果；相同块重复发送幂等 ACK，内容冲突失败 | LLM 推断 | 进程内续传及并发隔离要求稳定会话状态；避免同一会话并发重复调用上游 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | 影响边界各模块；`SC_01`、`SC_06`、`SC_07` |
| 状态 | `SC_02`、`SC_03`、`SC_11` 的进程内会话块、处理中和完成状态 |
| 时序 | `SC_01` ACK 后下行、`SC_08` 重试、`SC_09` 超时、`SC_11` 并发隔离 |
| 资源 | `SC_05` 载荷限制、`SC_10` socket 下行断开、sessions 原子文件写入 |
| 不变量 | `影响边界与不变量` |
| 故障 | `SC_04`、`SC_05`、`SC_08`、`SC_09`、`SC_10`、`SC_12` |

## 验收清单

### 单元测试

- [ ] 流式解码覆盖半包、粘包、流水线、BAD_MAGIC、BAD_CRC 和 PAYLOAD_TOO_LARGE。
- [ ] WAV 解析只接受 PCM16LE/单声道/16000Hz，正确跳过带 padding 的未知 chunk 并输出 PCM。
- [ ] 会话块覆盖顺序、幂等重复、冲突重复、缺块、sha256 失败、路径安全和多会话隔离。
- [ ] 编排覆盖成功、4xx、5xx 一次恢复、5xx 耗尽、超时和畸形 2xx 响应。
- [ ] 下行覆盖 ACK/TTS_CHUNK/TTS_END 顺序、块号、块大小、总数及 PCM sha256。

### Smoke 测试

- [ ] `python3 -m unittest discover -s fixture/backend -p 'test_*.py' -v` 全部通过。
- [ ] 启动 mock 与 backend 后，仿真设备上传 `ask_weather.wav`，ACK 含预期 text/reply，两个 WAV 文件与真源逐字节相符，下行 PCM 与 TTS WAV 的 data chunk 相符。

### E2E 测试

- 决策：需要
- 依据：任务跨 TCP 客户端、并发后端线程、三个 HTTP 路径、文件系统和故障注入，单元测试无法证明真实字节流与进程边界协作。
- [ ] 本地回环 E2E 覆盖天气、时间两会话并发，断线续传，流水线/半包/粘包，CRC/超长载荷，ASR 5xx 重试恢复、ASR 超时、未知音频 4xx 及下行断连隔离。

## 测试驱动开发

1. `SC_01`、`SC_04`、`SC_05` → 先写流式协议与错误帧测试。
2. `SC_02`、`SC_03`、`SC_06`、`SC_12` → 先写上传会话、完整性和安全边界测试。
3. `SC_08`、`SC_09` → 先写 HTTP 重试、超时与错误映射测试。
4. `SC_07`、`SC_10` → 先写 WAV 校验与下行完整性测试。
5. `SC_11`、`SC_13` → 先写多会话和完整跨进程测试。
6. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: 正常全链路返回可播放完整音频

- **GIVEN** 设备上传已收录、格式正确的 WAV，mock 服务健康
- **WHEN** 设备在一个 TCP 连接中发送 HELLO、连续 AUDIO_CHUNK 和 AUDIO_END
- **THEN** 后端依次 ACK 每帧；END ACK 含 `ok=true`、预期 text/reply；随后从 1 递增发送 PCM TTS_CHUNK，最后发送总数和完整 PCM sha256 相符的 TTS_END
- 测试层：e2e
- 依据：用户任务 / `J4`

### Scenario SC_02: 断线重连从连续断点续传

- **GIVEN** 某 session 已按序保存前 K 个上传块且连接断开
- **WHEN** 同一 session_id 重新 HELLO
- **THEN** HELLO ACK 的 `last_seq` 等于 K，后续块可继续上传并完成完整链路
- 测试层：e2e
- 依据：用户任务 / `J2`

### Scenario SC_03: 流水线半包粘包保持帧边界

- **GIVEN** 多个合法帧以任意网络分片组合到达且设备不等待块 ACK
- **WHEN** 后端流式读取连接
- **THEN** 每帧仅解析一次且按帧 seq 返回 ACK，重组文件与原文件逐字节一致
- 测试层：e2e
- 依据：用户任务 / `J1`

### Scenario SC_04: 魔数或 CRC 错误立即终止当前连接

- **GIVEN** 当前连接收到魔数错误或 CRC 不匹配的完整帧
- **WHEN** 解码器处理该帧
- **THEN** 后端分别返回 BAD_MAGIC(seq=0) 或 BAD_CRC(关联 seq) ERROR 并关闭连接，已确认块状态保留
- 测试层：unit
- 依据：用户任务 / `J1`

### Scenario SC_05: 超限载荷在读取主体前拒绝

- **GIVEN** 帧头声明 len 大于 262144 且不发送载荷主体
- **WHEN** 后端收到完整头部
- **THEN** 后端返回 PAYLOAD_TOO_LARGE ERROR 并关闭连接，不等待或分配声明载荷
- 测试层：e2e
- 依据：用户任务 / `J1`

### Scenario SC_06: 缺块或哈希不符禁止落盘与编排

- **GIVEN** AUDIO_END 的 total_chunks/sha256 与已收连续块不一致
- **WHEN** 后端处理 AUDIO_END
- **THEN** 返回 INTEGRITY_FAIL 并关闭连接，不写 `upload.wav`、不调用 ASR
- 测试层：unit
- 依据：用户任务 / `J2`

### Scenario SC_07: 下行使用受支持 PCM 格式

- **GIVEN** TTS 返回 WAV
- **WHEN** 后端准备下行
- **THEN** 后端校验 PCM16LE/单声道/16000Hz，`reply.wav` 保留原始 WAV，TTS_CHUNK 只承载其完整 data PCM；不支持的 WAV 转为 UPSTREAM_ERROR
- 测试层：unit
- 依据：用户任务 / `J4`

### Scenario SC_08: 5xx 按配置重试并有界失败

- **GIVEN** 任一上游首次或持续返回 5xx，`retry_max_5xx=1`
- **WHEN** 编排调用该上游
- **THEN** 首次 5xx 后最多再调用一次；恢复则继续链路，仍为 5xx 则返回 UPSTREAM_ERROR 且后续服务不调用
- 测试层：e2e
- 依据：用户任务 / `J3`

### Scenario SC_09: 上游超时和 4xx 均有限返回错误

- **GIVEN** 任一上游超过 `service_timeout_ms` 或返回 4xx
- **WHEN** 编排调用该上游
- **THEN** 超时不重试并返回 UPSTREAM_TIMEOUT，4xx 不重试并返回 UPSTREAM_ERROR，两者均关闭连接且不调用后续服务
- 测试层：e2e
- 依据：用户任务 / `J3`

### Scenario SC_10: 下行断开只结束当前会话连接

- **GIVEN** 一个设备在 ACK 后接收 TTS 下行时断开，另一个会话同时工作
- **WHEN** 后端发送后续 TTS 帧
- **THEN** 发送异常被当前处理线程吸收，服务进程继续接受连接，另一个会话完成
- 测试层：e2e
- 依据：用户任务

### Scenario SC_11: 多设备并发会话完全隔离

- **GIVEN** 两个 device/session 同时上传不同已收录 WAV
- **WHEN** 后端并发处理两条完整链路
- **THEN** 每个 ACK 的 text/reply、upload/reply 文件和下行 PCM 都匹配自身输入，目录及内存块无交叉
- 测试层：e2e
- 依据：用户任务 / `J7`

### Scenario SC_12: 会话标识与块序列异常受控失败

- **GIVEN** HELLO 含路径穿越 session_id，或块 seq 非连续、重复内容冲突、非尾块大小不符
- **WHEN** 后端处理对应帧
- **THEN** 返回 INTEGRITY_FAIL 并关闭连接，不在 `sessions/` 外写文件且不推进续传断点
- 测试层：unit
- 依据：`J2` / `J5` / `J6`

### Scenario SC_13: 结果文件具备确定性与原子可见性

- **GIVEN** 上传完整性和 TTS 响应均通过校验
- **WHEN** 后端写入 session 结果
- **THEN** `upload.wav` 与上传原始字节相同，`reply.wav` 与 TTS 原始响应相同，消费者只观察到完整目标文件
- 测试层：smoke
- 依据：用户任务 / `J5`
