> spec_version: 3

# voice-chain

## 任务目标

- 后端通过单个 TCP 连接完成 HELLO、可续传 WAV 上传、ASR→LLM→TTS 编排、结果落盘、应答 ACK 与可校验 PCM 下发。
- 多设备并发时，每个 `session_id` 的上传状态、识别文本、回复文本和落盘文件相互隔离。
- 协议错误和任一上游失败都在有限时间内向设备发送规范 ERROR 帧并关闭当前连接，服务继续处理其他会话。

## 非目标

- 不实现跨后端进程的断点持久化、真实 ESP32 固件或真实云服务接入。
- 不修改 `fixture/device-sim/`、`fixture/mock-services/`、`fixture/assets/` 及其确定性映射。
- 不扩展设备协议为多轮对话、下行续传、身份认证或传输加密。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/app.py` | 目标 | TCP 接入、会话状态、上传重组、上游编排、ACK/ERROR 与下发时序 | 同 session 并发或断线重连交错 → 块状态覆盖/串话 → 文件与应答归属错误 | 会话状态按 `session_id` 隔离；同一会话状态变更串行化；ACK 先于 TTS 下发；单连接失败不终止监听服务 | 用户任务，`J1`、`J2`、`J5` |
| `fixture/backend/protocol.py` | 目标 | 流式帧解析与规范错误分类 | 粘包、半包或超长声明 → 错帧被消费或无限缓冲 → 连接挂死/内存放大 | 只在完整帧后消费；CRC 覆盖 type+seq+len+payload；超限在等待 payload 前拒绝 | 用户任务，`J1` |
| `fixture/backend/http_client.py` | 目标 | HTTP 超时、状态返回与网络错误归一化 | 超时未转换或 5xx 重试无界 → 设备长期无应答 | 每次调用使用配置毫秒超时；4xx 不重试；5xx 最多额外重试配置次数；超时不重试 | 用户任务，`J3` |
| `fixture/backend/audio.py` | 目标 | 校验 TTS WAV 播放格式、提取 PCM、按规范块大小切分 | 仅剥离 WAV 头且忽略 fmt → 下发设备无法播放的 PCM | 只接受 PCM16/单声道/16000Hz WAV；下发内容为其完整 data 块且顺序不变 | 用户任务，`J4`、`J5` |
| `fixture/device-sim/device_sim.py` | 上游/下游 | 提供 HELLO、上传帧和消费 ACK/TTS 的真实进程链路 | ACK 或下行时序偏离 → 仿真设备阻塞或误读 | 文件保持只读；后端兼容其停等发送，同时支持规范允许的流水线发送 | 用户任务 |
| `fixture/mock-services/mock_services.py` | 下游 | 提供确定 ASR/LLM/TTS 与故障注入 | 错误分类或请求体变化 → 重试策略和确定性映射失效 | 文件保持只读；请求路径、内容类型、JSON 字段与响应体遵循规范 | 用户任务 |
| `sessions/<session_id>/` | 下游 | 保存逐字节上传 WAV 与原样 TTS WAV | 未原子完成或目录串用 → 消费者读到部分文件/跨会话文件 | `upload.wav` 等于完整上传字节；`reply.wav` 等于 TTS 响应 WAV；每个 session 使用独立目录 | 用户任务，`J2` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | 每个连接首帧为 HELLO；其后接受按 1 递增的 AUDIO_CHUNK，重复的已收块仅在内容一致时幂等 ACK；AUDIO_END 结束上传 | 用户任务 / LLM 推断 | wire protocol 固定 HELLO seq=0、块号从 1 递增并以最大已收块续传；连续前缀保证 `last_seq` 可作为安全断点 | 已确认 |
| J2 | 断线续传只保存进程内的连续块前缀；完成并通过哈希后写 `sessions/<session_id>/upload.wav` | 用户任务 | 题面明确允许进程内存续传，并要求落盘字节与原文件逐字节一致 | 已确认 |
| J3 | `retry_max_5xx` 表示首次请求失败后允许的额外重试次数；任一次超时立即停止该服务调用 | 用户任务 / LLM 推断 | “返回 5xx：重试，次数上限走配置”与配置值 1；按常见 retry 配置语义取最小可验证解释；超时明确不重试 | 已确认 |
| J4 | TTS 响应必须是 PCM、16 bit、小端、单声道、16000Hz 的 WAV，后端下发其中 PCM data；不满足时作为 `UPSTREAM_ERROR` | 用户任务 / LLM 推断 | mock TTS 声明返回 WAV，设备仅支持裸 PCM 参数；无独立音频格式错误码，错误发生在消费上游响应阶段 | 已确认 |
| J5 | 下行 PCM 使用 3200 字节块；TTS_END payload 为 `{"total_chunks": int, "sha256": <完整PCM十六进制摘要>}` | 规范 / LLM 推断 | 音频规范称播放数据“同样按块接收”，唯一规定块大小为 3200；设备必须能校验完整性，复用 AUDIO_END 的总块数与 sha256 形状形成最小对称契约 | 已确认 |
| J6 | 协议级 BAD_MAGIC、BAD_CRC、PAYLOAD_TOO_LARGE 与完整性失败均发送同名规范 ERROR 后关闭连接并保留已收块 | 用户任务 / 规范 | wire protocol 明确定义错误码、关闭语义与续传状态保留 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `SC_01`、`SC_07`、`SC_13` 覆盖上传字节、文本/回复、WAV 与 PCM 的转换和归属 |
| 状态 | `SC_02`、`SC_11` 覆盖连续断点与多会话隔离状态 |
| 时序 | `SC_01`、`SC_08`、`SC_13` 覆盖流水线接收、有限超时与 ACK 后下发顺序 |
| 资源 | `SC_11`、`SC_14` 覆盖线程/连接隔离和下行断连释放 |
| 不变量 | `影响边界与不变量` |
| 故障 | `SC_03` 至 `SC_06`、`SC_08` 至 `SC_10`、`SC_14` |

## 验收清单

### 单元测试

- [ ] 流式解码对半包、粘包输出完整有序帧，对坏 magic、坏 CRC、超限声明分别给出规范错误码。
- [ ] WAV 校验只接受 PCM16/单声道/16000Hz，提取完整 PCM 并生成含总块数与 sha256 的下行元数据。
- [ ] 上游调用对超时、4xx、一次可恢复 5xx 与耗尽 5xx 执行精确的停止/重试策略。
- [ ] 会话仅接受连续块前缀，断线重连返回安全 `last_seq`，多会话状态互不共享。

### Smoke 测试

- [ ] 启动 mock 与后端进程，仿真设备上传后核对 AUDIO_END ACK 文本、`upload.wav` 和 `reply.wav`。
- [ ] 自构造流水线/粘包/半包客户端完成上传，并核对逐块 ACK 与文件摘要。
- [ ] 注入上游超时、5xx、4xx 后在有限时间内收到正确 ERROR，随后正常会话仍成功。

### E2E 测试

- 决策：需要
- 依据：本任务包含 TCP 与 HTTP 两类跨进程协议、并发会话、断线续传及完整设备链路风险。
- [ ] 两个仿真设备并发完成上传→三服务编排→PCM 下发，分别核对 ACK、落盘和 TTS_END 摘要。
- [ ] 真实连接上传部分块后断开，同 session 重连从 HELLO ACK 断点完成全链路。
- [ ] 下发中主动断开一个设备连接，后端进程存活且另一会话完成。

## 测试驱动开发

1. `SC_03` 至 `SC_05` → 先写失败的流式协议错误单元测试。
2. `SC_02`、`SC_06`、`SC_11` → 先写失败的会话连续性、完整性与隔离测试。
3. `SC_08` 至 `SC_10` → 先写失败的 HTTP 超时/重试策略测试。
4. `SC_12`、`SC_13` → 先写失败的 WAV 格式与下行完整性测试。
5. `SC_01`、`SC_07`、`SC_14` → 启动本地进程跑正常、断连和服务存活 Smoke/E2E。
6. 实现满足测试的最小代码，重构后复跑全部 unit、smoke 与 e2e。

## Scenarios

### Scenario SC_01: 流水线字节流上传逐字节落盘

- **GIVEN** 有效 HELLO 后，设备把有效 WAV 的连续 AUDIO_CHUNK 以半包、粘包和无需等待 ACK 的方式发送
- **WHEN** 后端收到匹配总块数与完整文件 sha256 的 AUDIO_END
- **THEN** 每块收到对应空载荷 ACK，`upload.wav` 与原始 WAV 逐字节一致
- 测试层：smoke
- 依据：用户任务，`J1`、`J2`

### Scenario SC_02: 断线后从连续断点完成全链路

- **GIVEN** 某 session 已收到前 N 个连续块后 TCP 断开且后端进程仍运行
- **WHEN** 同 session_id 重连发送 HELLO 并从返回的 `last_seq=N` 继续上传到 AUDIO_END
- **THEN** 后端仅组合一次完整文件并继续完成 ASR→LLM→TTS、ACK 与下发
- 测试层：e2e
- 依据：用户任务，`J1`、`J2`

### Scenario SC_03: 坏魔数获得错误并关闭连接

- **GIVEN** 当前连接收到帧头 magic 不是 `0xA55A`
- **WHEN** 流式解码器检查帧头
- **THEN** 设备收到 code=`BAD_MAGIC` 的 ERROR，连接关闭且服务进程继续运行
- 测试层：unit
- 依据：用户任务，`J6`

### Scenario SC_04: 坏 CRC 获得错误并关闭连接

- **GIVEN** 当前连接收到完整帧且 CRC32 与 type+seq+len+payload 不匹配
- **WHEN** 流式解码器校验帧
- **THEN** 设备收到 code=`BAD_CRC` 的 ERROR，连接关闭且服务进程继续运行
- 测试层：unit
- 依据：用户任务，`J6`

### Scenario SC_05: 超限载荷声明立即拒绝

- **GIVEN** 当前连接收到 len 大于 262144 的完整帧头且 payload 尚未到达
- **WHEN** 流式解码器读取 len
- **THEN** 设备收到 code=`PAYLOAD_TOO_LARGE` 的 ERROR，后端不等待 payload 并关闭连接
- 测试层：unit
- 依据：用户任务，`J6`

### Scenario SC_06: 上传摘要不匹配拒绝编排

- **GIVEN** 已收到 AUDIO_END 声明数量对应的连续块且重组 sha256 与声明值不同
- **WHEN** 后端处理 AUDIO_END
- **THEN** 设备收到 code=`INTEGRITY_FAIL` 的 ERROR，连接关闭，不调用 ASR 且会话块状态保留
- 测试层：smoke
- 依据：用户任务，`J2`、`J6`

### Scenario SC_07: 成功编排落盘并扩展 ACK

- **GIVEN** ask_weather.wav 完整性校验通过且三个 mock 服务正常
- **WHEN** 后端依次完成 ASR、LLM、TTS
- **THEN** `reply.wav` 逐字节等于 mock TTS WAV，AUDIO_END ACK 为 `{"ok":true,"text":"今天天气怎么样","reply":"今天晴，气温二十六度"}`
- 测试层：smoke
- 依据：用户任务

### Scenario SC_08: 上游超时有限返回

- **GIVEN** 任一 ASR、LLM 或 TTS 调用超过配置 `service_timeout_ms`
- **WHEN** HTTP 调用触发超时
- **THEN** 后端不重试并在有限时间内发送 code=`UPSTREAM_TIMEOUT` 的 ERROR 后关闭连接
- 测试层：smoke
- 依据：用户任务，`J3`

### Scenario SC_09: 一次 5xx 后重试成功

- **GIVEN** 任一上游首次返回 5xx、下一次正常且 `retry_max_5xx=1`
- **WHEN** 后端执行该服务调用
- **THEN** 后端额外重试一次并继续完成当前会话全链路，不发送 ERROR
- 测试层：unit
- 依据：用户任务，`J3`

### Scenario SC_10: 上游不可恢复错误停止编排

- **GIVEN** 任一上游返回 4xx，或在允许的 5xx 重试后仍返回 5xx
- **WHEN** 后端执行该服务调用
- **THEN** 4xx 不重试、5xx 不超过配置额外重试次数，两者均发送 code=`UPSTREAM_ERROR` 的 ERROR 并关闭连接
- 测试层：unit
- 依据：用户任务，`J3`

### Scenario SC_11: 多设备并发会话隔离

- **GIVEN** 两个不同 session_id 同时上传 ask_weather.wav 与 ask_time.wav
- **WHEN** 两条连接并发完成编排
- **THEN** 各自 ACK 文本/回复、upload.wav、reply.wav 与下行 PCM 均匹配自己的输入且无交叉内容
- 测试层：e2e
- 依据：用户任务

### Scenario SC_12: TTS WAV 格式受设备能力约束

- **GIVEN** TTS 返回 WAV
- **WHEN** 后端解析其 fmt 与 data 块
- **THEN** 仅 PCM16/小端/单声道/16000Hz 产生下行 PCM；格式或结构不符时发送 code=`UPSTREAM_ERROR` 的 ERROR
- 测试层：unit
- 依据：用户任务，`J4`

### Scenario SC_13: ACK 后下发可完整校验的 PCM

- **GIVEN** TTS 返回有效回复 WAV 且 AUDIO_END ACK 已发送
- **WHEN** 后端下发回复音频
- **THEN** 从 1 递增的 TTS_CHUNK 按 3200 字节承载完整 PCM，随后 TTS_END seq 等于总块数且 payload 的 total_chunks 与 sha256 匹配该 PCM
- 测试层：e2e
- 依据：用户任务，`J5`

### Scenario SC_14: 下发断连只结束当前会话

- **GIVEN** 一个设备在 TTS_CHUNK 下发过程中关闭连接，另一个会话同时处理
- **WHEN** 后端写入已断开的 socket 失败
- **THEN** 当前连接线程释放且后端进程保持存活，另一会话的 ACK、文件和下发完整成功
- 测试层：e2e
- 依据：用户任务
