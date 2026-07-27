> spec_version: 3

# voice-chain

## 任务目标

- 后端在既有启动契约下接收设备的 HELLO、音频块和结束帧，处理 TCP 粘包、半包与流水线发送，并在 `sessions/<session_id>/upload.wav` 保存逐字节等同原始上传的 WAV 文件。
- 完整性校验成功后，后端按 ASR、LLM、TTS 的顺序调用配置的服务，将原始 TTS WAV 保存为 `sessions/<session_id>/reply.wav`，并把识别文本与回复文本放入 AUDIO_END 的 ACK。
- AUDIO_END 的 ACK 写入 socket 后，后端将 TTS WAV 提取为设备可播放的 PCM 数据，以连续 TTS_CHUNK 和含完整性元数据的 TTS_END 下发同一连接。
- 会话、落盘文件、上游结果和连接故障在多设备并发场景保持隔离；每种协议或上游故障都在配置的有限时间内形成 ERROR 帧或受控断连。

## 非目标

- ESP32 固件、设备播放实现与设备模拟器改动。
- 云端 ASR、LLM、TTS 服务接入。
- 跨后端进程的断线续传持久化。
- 音频编解码、语音合成模型与用户界面。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|
| `fixture/backend/app.py` | 目标 | 连接状态机、进程内会话表、音频重组、服务编排、落盘与下行发送 | 每条连接只消费自身解码器和 socket；同一 session 的块状态原子更新；错误帧发送后连接关闭 | 用户任务、`J2`、`J7` |
| `fixture/backend/protocol.py` | 相关 | 由连接处理调用流式解码和帧编码 | 帧字段、CRC、网络字节序和 `BAD_MAGIC`、`BAD_CRC`、`PAYLOAD_TOO_LARGE` 语义保持规范一致 | `J2` |
| `fixture/backend/http_client.py` | 下游 | 提供 ASR、LLM、TTS 的带超时 HTTP 调用 | 每次请求使用 `service_timeout_ms`；4xx、5xx、超时可区分；5xx 重试次数受配置约束 | `J1`、`J8` |
| `fixture/backend/audio.py` | 下游 | 将 TTS WAV 解析为播放器所需 PCM 并按播放块切分 | 下行载荷是 16-bit little-endian、单声道、16 kHz PCM；回复 WAV 原始字节独立保留 | `J3`、`J4` |
| `fixture/backend/config.json` | 上游 | 为服务地址、超时和 5xx 重试次数提供配置 | 端口、超时、重试和服务地址只有此配置与题面规范两个真源 | `J1` |
| `fixture/device-sim/device_sim.py` | 上游/下游 | 维持 HELLO ACK、AUDIO_END ACK 后接收 TTS 帧的现有交互 | 后端启动入口、ACK seq 语义、上传字节和下行帧顺序保持兼容 | 用户任务、`J2` |
| `fixture/mock-services/mock_services.py` | 下游 | 作为确定性 ASR、LLM、TTS 与故障注入服务 | 后端只使用已声明的 HTTP 接口；每个会话结果只由该会话的上游应答决定 | `J5`、`J8` |
| `sessions/<session_id>/` | 相关 | 保存 upload.wav 和 reply.wav | 文件归属单一会话；upload.wav 与完整上传逐字节一致；reply.wav 与 TTS HTTP 成功体逐字节一致 | 用户任务、`J6`、`J7` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | 服务地址、调用超时与 5xx 重试上限从 config.json 读取，超时值由毫秒换算给 HTTP 客户端 | 仓库事实 | `backend/config.json` 给出 `mock_base_url`、`service_timeout_ms`、`retry_max_5xx`；`http_client.post` 接收 `timeout_ms` | 已确认 |
| J2 | TCP 接收端必须以长寿命 FrameDecoder 累积字节，并在每次 recv 后顺序处理已完成帧 | 题面规范 | wire-protocol 明确 TCP 是字节流，允许粘包、半包与连续发送；骨架的 `FrameDecoder.feed()` 支持任意片段 | 已确认 |
| J3 | 上传文件按完整 WAV 字节流重组；设备播放载荷使用 PCM 裸流和 3200 字节块 | 题面规范 | audio-format 区分上传完整 WAV 与播放 PCM，且给出每块 3200 字节 | 已确认 |
| J4 | TTS HTTP 返回的 WAV 先保存为 reply.wav，再经 wav_pcm 提取 PCM 后下发 | 题面规范与仓库事实 | mock `/tts` 返回 `audio/wav`；设备能力只覆盖 PCM；`audio.wav_pcm` 已提供 RIFF data 块提取 | 已确认 |
| J5 | ASR、LLM、TTS 串行编排，前一步输出是后一步输入，AUDIO_END ACK 同时返回 ASR text 和 LLM reply | 题面规范 | 02-orchestration.md 定义调用顺序、reply.wav 和 ACK payload | 已确认 |
| J6 | TTS_END 使用 JSON `{"total_chunks": int, "sha256": str}`，sha256 覆盖完整下行 PCM 字节 | LLM 推断 | 03-downlink 要求设备校验完整性；wire-protocol 未指定 TTS_END payload。该结构沿用 AUDIO_END 的可验证字段形态 | 待确认 |
| J7 | 会话表以 session_id 分桶，单个会话在块写入、结束校验和落盘期间持有会话级互斥；连接关闭不清除已收块 | 题面规范 | 全链路要求多设备隔离与内存断线续传；wire-protocol 要求 ERROR 后关闭连接且保留已收块会话状态 | 已确认 |
| J8 | 5xx 最多执行 `retry_max_5xx` 次额外尝试；4xx 和超时零重试；耗尽或调用异常统一回受控 ERROR | 题面规范与 LLM 推断 | 02-orchestration.md 定义三类策略，配置字段名称为 retry_max_5xx；“次数上限”作为额外重试次数需在实现和测试中固定 | 待确认 |
| J9 | 服务级故障必须由当前连接回 ERROR，随后关闭该连接，其他会话线程继续处理 | 题面规范 | 全链路与协议规范要求上游失败有 ERROR、无挂死、已收块会话保留 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `Scenario: 全链路成功与落盘`、`Scenario: TTS PCM 下行与完整性结束帧` |
| 状态 | `影响边界与不变量` 的会话表约束、`Scenario: 断线续传`、`Scenario: 下行断线隔离` |
| 时序 | `Scenario: 粘包与流水线上传`、`Scenario: ACK 后下行`、`Scenario: 上游超时` |
| 资源 | `影响边界与不变量` 的 socket 与会话文件所有权、`Scenario: 下行断线隔离` |
| 不变量 | `影响边界与不变量` |
| 故障 | `Scenario: 协议错误`、`Scenario: 上游超时`、`Scenario: 上游 HTTP 错误与重试`、`Scenario: 下行断线隔离` |

## 验收清单

### 单元测试

- [ ] 为 FrameDecoder 覆盖半包、粘包、错误魔数、错误 CRC 与超载荷，并断言对应 ProtocolError code。
- [ ] 为会话块表覆盖重复块、顺序重组、HELLO 的 last_seq、断线后续传和 SHA-256 失败。
- [ ] 为 ASR→LLM→TTS 调用序列覆盖成功体解析、毫秒超时、4xx 零重试、5xx 的配置次数重试和 ERROR 映射。
- [ ] 为 TTS WAV 保存、PCM 提取、3200 字节下行分块、TTS_END 总块数与 SHA-256 覆盖。
- [ ] 为两个 session 的并行上传与一条下行断连覆盖独立的内存状态、文件路径和 socket 生命周期。

### Smoke 测试

- [ ] 在 `fixture/mock-services/` 启动 `python3 mock_services.py --port 9100`，在 `fixture/backend/` 启动 `python3 app.py --port 9000 --config config.json`，再运行 `python3 device-sim/device_sim.py --server 127.0.0.1:9000 --wav assets/ask_weather.wav`；检查 ACK 的 text/reply、两个会话文件和设备输出字节。
- [ ] 通过 `/control` 注入 500 与 hang_ms，检查设备在配置超时内收到 `UPSTREAM_ERROR` 或 `UPSTREAM_TIMEOUT`，且服务端继续接收下一条会话。

### E2E 测试

- 决策：需要
- 依据：该链路跨 TCP 客户端、线程化后端、三个 HTTP 服务、会话文件系统和下行帧；单元测试无法证明 ACK 与下行的真实 socket 顺序及并发隔离。
- [ ] 两个设备模拟器使用不同 session 并发上传，分别接收可校验的 PCM 下行；再让一个设备在下行阶段断开，检查另一会话完成。

## 测试驱动开发

1. `粘包与流水线上传`、`协议错误`、`断线续传` → 先写 FrameDecoder、会话块表与错误帧的单元测试。
2. `全链路成功与落盘`、`上游超时`、`上游 HTTP 错误与重试` → 先写 HTTP 编排和错误映射的单元测试。
3. `ACK 后下行`、`TTS PCM 下行与完整性结束帧`、`下行断线隔离` → 先写 socket 写入顺序、PCM 分块和连接隔离的单元测试。
4. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario: 粘包与流水线上传

- **GIVEN** 已通过 HELLO 建立新会话，客户端将多个 AUDIO_CHUNK 连续写入同一 TCP 字节流，任一帧可跨多次 recv 或与相邻帧粘连
- **WHEN** 后端持续接收并喂给该连接的 FrameDecoder
- **THEN** 后端按帧的 seq 收集块、对每个已接收块返回对应 seq 的 ACK，且每块只进入当前 session 的缓冲区一次
- 测试层：unit
- 依据：`J2`、`J7`

### Scenario: 断线续传

- **GIVEN** session 已持有从 1 连续到 N 的音频块，原连接已关闭
- **WHEN** 设备以同一 session_id 重新发送 HELLO
- **THEN** HELLO ACK 的 seq 为 0 且 payload 的 last_seq 为 N；设备从 N+1 继续后，重组顺序仍为 1 到 total_chunks
- 测试层：unit
- 依据：`J7`

### Scenario: 协议错误

- **GIVEN** 已连接客户端发送魔数错误、CRC 错误或声明长度超过 MAX_PAYLOAD 的帧
- **WHEN** 后端解码该字节流
- **THEN** 后端发送 code 分别为 BAD_MAGIC、BAD_CRC 或 PAYLOAD_TOO_LARGE 的 ERROR，关闭当前连接，并保留已有会话块状态
- 测试层：unit
- 依据：`J2`、`J9`

### Scenario: 上传完整性失败

- **GIVEN** 当前会话已收到 total_chunks 所声明数量的块，AUDIO_END 的 sha256 与重组字节不一致
- **WHEN** 后端处理 AUDIO_END
- **THEN** 后端不写成功的 upload.wav、不调用 ASR，并发送 code 为 INTEGRITY_FAIL 的 ERROR 后关闭当前连接
- 测试层：unit
- 依据：用户任务、`J7`

### Scenario: 全链路成功与落盘

- **GIVEN** 一个完整上传通过 SHA-256 校验，三个 mock 服务分别成功返回 text、reply 和 TTS WAV
- **WHEN** 后端处理 AUDIO_END
- **THEN** `upload.wav` 与原始上传字节一致，调用顺序为 ASR、LLM、TTS，`reply.wav` 与 TTS HTTP 响应字节一致，AUDIO_END ACK payload 含 ok=true、text 和 reply
- 测试层：e2e
- 依据：`J4`、`J5`

### Scenario: 上游超时

- **GIVEN** 任一 ASR、LLM 或 TTS 调用超过 config 的 service_timeout_ms
- **WHEN** 后端执行该服务调用
- **THEN** 该调用执行零次重试，设备在有限时间内收到 code 为 UPSTREAM_TIMEOUT 的 ERROR，当前连接关闭，其他会话继续运行
- 测试层：smoke
- 依据：`J1`、`J8`、`J9`

### Scenario: 上游 HTTP 错误与重试

- **GIVEN** 任一服务先返回 5xx 或返回 4xx
- **WHEN** 后端处理该响应
- **THEN** 5xx 在每次尝试使用相同请求体的前提下最多额外重试 retry_max_5xx 次，4xx 执行零次重试；耗尽或收到 4xx 后设备收到 code 为 UPSTREAM_ERROR 的 ERROR
- 测试层：unit
- 依据：`J1`、`J8`

### Scenario: 并发会话隔离

- **GIVEN** 两台设备使用不同 session_id 并发上传不同 WAV，两个连接的块和上游调用时间交错
- **WHEN** 后端完成两条 AUDIO_END
- **THEN** 每条 ACK 的 text/reply、upload.wav、reply.wav 和下行 PCM 只对应自己的输入会话，任一会话缓冲不含另一 session 的字节
- 测试层：e2e
- 依据：`J5`、`J7`

### Scenario: ACK 后下行

- **GIVEN** TTS WAV 已成功保存且当前 socket 仍连接
- **WHEN** 后端完成 AUDIO_END 处理
- **THEN** socket 观察到 AUDIO_END ACK 完整写出后才出现第一个 TTS_CHUNK，所有 TTS_CHUNK 的 seq 从 1 连续递增，TTS_END 的 seq 等于总块数
- 测试层：unit
- 依据：用户任务、`J4`

### Scenario: TTS PCM 下行与完整性结束帧

- **GIVEN** TTS 返回符合设备播放格式的 WAV
- **WHEN** 后端下发回复音频
- **THEN** 拼接的 TTS_CHUNK payload 等于 reply.wav 的 PCM data 块，单块长度最多 3200 字节，TTS_END 的 total_chunks 与 sha256 能校验该完整 PCM 字节流
- 测试层：unit
- 依据：`J3`、`J4`、`J6`

### Scenario: 下行断线隔离

- **GIVEN** 会话 A 在收到部分 TTS_CHUNK 后断开，独立会话 B 正在上传或下行
- **WHEN** 后端向会话 A 的 socket 写入下一帧发生连接错误
- **THEN** 会话 A 的线程受控结束且不终止服务器进程；会话 B 继续完成自身 ACK、文件落盘和下行链路
- 测试层：e2e
- 依据：`J7`、`J9`
