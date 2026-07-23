> spec_version: 3

# voice-chain

## 任务目标

- 后端通过 TCP 在一次连接中完成 HELLO、WAV 分块上传、完整性校验、ASR→LLM→TTS 编排、结果落盘以及可播放 PCM 下发。
- 同一进程内使用相同 `session_id` 重连时，从已经连续接收的最后块继续上传，并仍能完成应答与下发。
- 多连接并发处理时，每个会话的上传块、识别文本、回复文本和文件彼此隔离；单连接失败不终止监听服务或其他连接。
- 协议错误与任一上游失败在有限时间内产生规范 ERROR 帧并关闭当前连接。

## 非目标

- 不实现跨进程续传、会话数据库、鉴权、TLS、真云服务或真实 ESP32 固件。
- 不修改设备仿真器、mock 服务、音频素材和 pipeline skills。
- 不支持规范之外的 WAV 编码、声道数或采样率转换。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/protocol.py` | 目标 | 流式解析与帧编码 | 半包、粘包或恶意长度 → 错误解析/无限等待 → 连接挂死或串帧 | CRC 覆盖 `type+seq+len+payload`；载荷不超过 262144；每个完整合法帧仅产出一次 | `J1` |
| `fixture/backend/app.py` 上传状态 | 目标 | HELLO、分块接收、续传、校验和落盘 | 并发重连相同会话或乱序块 → 状态覆盖/缺块 → 文件损坏 | 会话状态按 `session_id` 隔离并加锁；只提交从 1 连续到总块数的字节；上传文件与原始 WAV 逐字节一致 | `J2`、`J3` |
| `fixture/backend/http_client.py` 与编排 | 目标 | 依次调用 ASR、LLM、TTS | 超时/5xx/4xx处理混淆 → 超额重试或无应答 → 设备挂死 | 调用顺序固定；超时不重试；4xx不重试；5xx最多追加配置次数；失败停止后续调用 | `J4`、`J5` |
| `fixture/backend/audio.py` 与下行 | 目标 | 校验 TTS WAV、提取 PCM、分块和结束校验元数据 | 直接下发 WAV 头或格式错误 → 设备无法播放；断线写入 → 线程异常扩散 | 下行仅为 16-bit 小端、单声道、16000 Hz PCM；块序号从 1 连续递增；结束帧可校验完整性 | `J6`、`J7` |
| `fixture/device-sim/device_sim.py` | 下游 | 消费 ACK、ERROR、TTS_CHUNK、TTS_END | ACK/下行顺序错误 → 客户端误判或等待 | AUDIO_END ACK 先于首个 TTS_CHUNK；帧格式符合 wire protocol | 用户任务 |
| `fixture/mock-services/mock_services.py` | 下游服务 | 接收三个确定性 HTTP 调用 | 请求体或 Content-Type 错误 → 4xx → 全链失败 | ASR 接收完整 WAV；LLM/TTS 接收 UTF-8 JSON；成功载荷原样消费 | `J4` |
| `sessions/<session_id>/` | 相关资源 | 保存 `upload.wav` 与 `reply.wav` | 非原子写入或跨会话路径串扰 → 残缺文件/越界写入 | session_id 经路径安全校验；文件先写临时文件再原子替换；reply 保留 mock 返回的完整 WAV 字节 | `J8` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | `MAX_PAYLOAD=262144`、魔数、大小端、CRC 算法和帧类型以 `wire-protocol.md` 为唯一协议真源 | 用户任务 | `task/specs/wire-protocol.md` 明确定义 | 已确认 |
| J2 | HELLO 返回的 `last_seq` 采用从 1 开始连续已接收块的最大序号；块号必须从 1 严格连续，重复的已确认块仅在内容一致时幂等 ACK | LLM 推断 | 续传端从 `last_seq+1` 发送；连续前缀可避免缺口永久跳过。规范规定块号从 1 递增 | 已确认 |
| J3 | `session_id` 首次 HELLO 时绑定 `device_id`；同一 session 的重连串行修改状态，其他 device_id 不能接管 | LLM 推断 | 满足多设备互不串扰与续传的一致所有权；采用最小安全隔离策略 | 已确认 |
| J4 | 三个服务依次调用 `/asr`、`/llm`、`/tts`，请求和成功响应严格采用 `mock-services.md` 形状 | 用户任务 | `task/02-orchestration.md` 与服务规范明确定义 | 已确认 |
| J5 | `retry_max_5xx` 表示初次请求之外允许的最大重试次数；每次尝试均受 `service_timeout_ms` 限制 | LLM 推断 | “重试次数上限”通常指追加尝试，配置名带 `retry`；单位由题面确认为毫秒 | 已确认 |
| J6 | TTS 服务返回完整 WAV 保存为 `reply.wav`，下发时剥离 WAV 容器并校验其 PCM 参数 | 用户任务 | TTS 接口返回 WAV；设备只支持裸 PCM 播放参数 | 已确认 |
| J7 | TTS_END 载荷使用 UTF-8 JSON `{"total_chunks": int, "sha256": <全部下发PCM的sha256>}`，seq 等于总块数 | LLM 推断 | 规范要求设备可校验完整无缺，同时将 TTS_END 载荷细节留白；该最小元数据复用上传完整性语义 | 已确认 |
| J8 | session_id 仅接受非空的 ASCII 字母、数字、点、下划线和连字符，长度 1..128；违反时发送带说明的 ERROR | LLM 推断 | session_id 直接参与文件路径；白名单阻止路径穿越，长度上限抑制资源滥用 | 已确认 |
| J9 | 语义无效、顺序错误、未知帧或格式错误的 WAV 使用 ERROR `code=INTEGRITY_FAIL`；该连接随后关闭并保留已确认上传块 | LLM 推断 | wire protocol 未分配通用协议语义错误码；现有错误码中该码最接近组装/内容无效，且所有错误都要求 ERROR 后关闭 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | 影响边界表，以及 `SC_05`、`SC_08`、`SC_09` |
| 状态 | `SC_02`、`SC_03`、`SC_04`、`SC_13` |
| 时序 | `SC_01`、`SC_02`、`SC_08`、`SC_10`、`SC_11` |
| 资源 | `SC_04`、`SC_05`、`SC_12`、`SC_13` |
| 不变量 | `影响边界与不变量` |
| 故障 | `SC_06`、`SC_07`、`SC_10`、`SC_11`、`SC_12` |

## 验收清单

### 单元测试

- [ ] 流式解码覆盖半包、粘包、坏魔数、坏 CRC 和超限声明。
- [ ] WAV 解析只接受 16-bit 小端、单声道、16000 Hz PCM，并按 3200 字节产生含短尾块的下行。
- [ ] 上传状态覆盖顺序块、内容一致的重复块、缺块、错误摘要、续传和并发会话隔离。
- [ ] 编排覆盖成功、4xx、可恢复/耗尽的 5xx、超时和传输错误，并断言调用次数与短路顺序。

### Smoke 测试

- [ ] 启动 mock 服务和后端，使用 `ask_weather.wav --upload-only` 完成上传，ACK 含预期 text/reply，`upload.wav` 与源文件逐字节一致且 `reply.wav` 与 mock TTS WAV 一致。
- [ ] 去掉 `--upload-only` 完成全链，下行拼接结果等于 TTS WAV 的 PCM data，TTS_END 块数和 sha256 匹配。

### E2E 测试

- 决策：需要
- 依据：链路跨 TCP 客户端、并发线程、后端文件系统和三个本地 HTTP 服务，单元替身无法覆盖帧时序与真实断线行为。
- [ ] 自动化回环 E2E 覆盖正常全链、流水线粘包、上传断线续传、双设备并发、坏帧、上游 4xx/5xx/超时和下行断开隔离。

## 测试驱动开发

1. `SC_01`、`SC_06` → 先写协议流式与坏帧单元测试。
2. `SC_02`、`SC_03`、`SC_04`、`SC_05` → 先写上传状态、续传、完整性与落盘测试。
3. `SC_10`、`SC_11` → 先写 HTTP 重试、超时和错误映射测试。
4. `SC_08`、`SC_09` → 先写编排成功和 PCM 下行测试。
5. `SC_12`、`SC_13` → 先写断线隔离和双设备并发 E2E。
6. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: 半包粘包保持帧边界

- **GIVEN** 多个合法 HELLO/AUDIO_CHUNK 帧被拼接且在任意字节处分段
- **WHEN** 字节片段依次输入流式解码器
- **THEN** 解码器按线序恰好产出每个原始帧一次，type、seq、payload 均一致
- 测试层：unit
- 依据：`J1`

### Scenario SC_02: 流水线上传逐块确认

- **GIVEN** 已完成 HELLO 且设备按 1..N 连续发送多个 AUDIO_CHUNK，无需等待逐个 ACK
- **WHEN** 后端处理这些帧
- **THEN** 每块得到同 seq 空载荷 ACK，会话连续 `last_seq` 最终为 N
- 测试层：e2e
- 依据：用户任务、`J2`

### Scenario SC_03: 断线后从连续断点续传

- **GIVEN** 会话已确认前 K 块并断线，进程仍运行
- **WHEN** 同 device_id、session_id 重新 HELLO
- **THEN** HELLO ACK 为 `{"last_seq": K}`，从 K+1 继续后可完成全链
- 测试层：e2e
- 依据：`J2`、`J3`

### Scenario SC_04: 完整 WAV 校验后原样落盘

- **GIVEN** 1..N 块完整且 AUDIO_END 的 total_chunks、seq、sha256 均匹配
- **WHEN** 后端处理 AUDIO_END
- **THEN** `sessions/<session_id>/upload.wav` 与上传原字节逐字节一致，并开始 ASR 调用
- 测试层：e2e
- 依据：用户任务

### Scenario SC_05: 缺块或摘要错误拒绝提交

- **GIVEN** AUDIO_END 声明的块集合不完整，或 sha256 与重组字节不符
- **WHEN** 后端处理 AUDIO_END
- **THEN** 设备收到关联 seq 的 `INTEGRITY_FAIL` ERROR，连接关闭且不调用 ASR
- 测试层：unit
- 依据：用户任务、`J9`

### Scenario SC_06: 非法传输帧返回精确错误

- **GIVEN** 帧分别具有错误魔数、错误 CRC 或超过 262144 的声明长度
- **WHEN** 后端解码该帧
- **THEN** 分别发送 `BAD_MAGIC`、`BAD_CRC`、`PAYLOAD_TOO_LARGE` ERROR 后关闭连接
- 测试层：unit
- 依据：`J1`

### Scenario SC_07: 非法会话路径被隔离

- **GIVEN** HELLO 的 session_id 为空、过长或包含斜杠等白名单外字符
- **WHEN** 后端处理 HELLO
- **THEN** 设备收到 ERROR 后连接关闭，且 `sessions` 外没有创建文件
- 测试层：unit
- 依据：`J8`、`J9`

### Scenario SC_08: 三服务成功编排并应答

- **GIVEN** 上传完整性通过且 ASR、LLM、TTS 均返回 200
- **WHEN** 后端完成 AUDIO_END 处理
- **THEN** 三服务按序各调用一次，`reply.wav` 与 TTS 响应逐字节一致，AUDIO_END ACK 为 `{"ok":true,"text":<ASR文本>,"reply":<LLM回复>}`
- 测试层：e2e
- 依据：`J4`

### Scenario SC_09: 回复转换为可校验 PCM 下行

- **GIVEN** TTS 返回符合规范且 PCM 长度不是 3200 整数倍的 WAV
- **WHEN** AUDIO_END ACK 已发送
- **THEN** 后端按 3200 字节发送 seq 从 1 连续递增的 TTS_CHUNK，最后短块完整，TTS_END 的 seq/total_chunks 和全部 PCM sha256 一致
- 测试层：e2e
- 依据：`J6`、`J7`

### Scenario SC_10: 5xx 仅按配置重试

- **GIVEN** 任一上游返回 5xx，`retry_max_5xx=1`
- **WHEN** 后端调用该服务
- **THEN** 最多调用两次；第二次成功则继续链路，第二次仍失败则返回 `UPSTREAM_ERROR` 且不调用后续服务
- 测试层：unit
- 依据：`J5`

### Scenario SC_11: 超时与 4xx 有限失败

- **GIVEN** 任一上游单次调用超过 `service_timeout_ms`，或返回 4xx
- **WHEN** 后端调用该服务
- **THEN** 超时返回 `UPSTREAM_TIMEOUT`、4xx 返回 `UPSTREAM_ERROR`，均不重试且停止后续服务
- 测试层：e2e
- 依据：用户任务、`J5`

### Scenario SC_12: 下行断开保持服务可用

- **GIVEN** 一个设备在收到 AUDIO_END ACK 后的 TTS_CHUNK 下发过程中断开
- **WHEN** 后端写 socket 失败
- **THEN** 当前连接处理线程结束，监听进程仍存活，另一会话可完成全链
- 测试层：e2e
- 依据：用户任务

### Scenario SC_13: 双设备并发会话隔离

- **GIVEN** 两个 device_id 使用不同 session_id 并发上传不同已收录 WAV
- **WHEN** 两条链路交错执行
- **THEN** 每条 ACK 的 text/reply 与自身音频匹配，各自 upload/reply 文件匹配对应素材，无跨会话值或文件覆盖
- 测试层：e2e
- 依据：用户任务、`J3`
