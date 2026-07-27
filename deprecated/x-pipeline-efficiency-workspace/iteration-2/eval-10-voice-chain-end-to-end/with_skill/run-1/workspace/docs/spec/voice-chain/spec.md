> spec_version: 3

# voice-chain

## 任务目标

- 后端在一条 TCP 连接内完成 HELLO、WAV 上传、完整性校验、ASR → LLM → TTS 编排，以及可播放 PCM 下发。
- 同一 `session_id` 断线重连时从进程内连续上传断点恢复，多设备并发会话的数据、结果和故障相互隔离。
- 协议错误或任一上游失败在有限时间内向设备发送规范 ERROR 帧并关闭当前连接；成功结果按会话落盘且可复跑验证。

## 非目标

- 不实现跨后端进程的断点持久化、生产云服务接入、身份认证、传输加密和真实 ESP32 固件。
- 不修改仿真设备、假服务和音频素材；这些目录仅作为测试设施。
- 不为同一 `session_id` 的多个设备建立独立会话；该标识按协议承担全局会话键职责。

## 影响边界与不变量

| 模块 | 角色 | 本次影响 | 主要风险 | 必须保持的不变量 | 依据 |
|---|---|---|---|---|---|
| `fixture/backend/protocol.py` | 目标 | 流式解码和帧编码 | 半包、粘包或坏长度触发解析错位 → 后续帧被误读 → 连接挂死或串帧 | CRC 只覆盖 `type + seq + len + payload`；payload 上限 262144；非法帧映射规范错误码 | 用户任务 |
| `fixture/backend/app.py` 连接处理 | 目标 | 会话恢复、上传、编排、ACK/ERROR 与下发 | 并发共享可变状态或异常逸出 → 会话串扰或处理线程无应答退出 | 每个 `session_id` 独占其块、文件、文本和回复；错误关闭只影响当前连接；成功 AUDIO_END ACK 先于下行 | 用户任务 / `J1` / `J4` |
| `fixture/backend/http_client.py` | 目标 | 标准库 HTTP 调用和超时分类 | 毫秒误作秒或异常未归类 → 设备等待过久或收不到 ERROR | 每次调用使用配置毫秒值；超时不重试；4xx 不重试；5xx 最多按配置追加重试 | 用户任务 / `J2` |
| `fixture/backend/audio.py` | 目标 | 校验 TTS WAV 并抽取设备 PCM | 直接下发 WAV 头或格式不符 → 设备产生噪声或无法播放 | 下行仅为 PCM 16-bit little-endian、mono、16000 Hz；块大小 3200，末块可短 | 用户任务 / `J3` |
| `fixture/device-sim/` | 上游/下游 | 发送上传协议并接收回复 | 服务端 ACK/下行次序偏离 → 客户端状态机阻塞 | HELLO ACK 给连续断点；每个已接收块有 ACK；AUDIO_END ACK 后才出现 TTS 帧 | 用户任务 |
| `fixture/mock-services/` | 下游 | 提供 ASR/LLM/TTS 与故障注入 | 重试边界错误 → 调用过多或过早失败 | ASR 使用完整原始 WAV；LLM/TTS 使用 JSON；返回音频原样落盘为 `reply.wav` | 用户任务 / `J2` |
| `sessions/<session_id>/` | 下游 | 保存 `upload.wav` 与 `reply.wav` | 路径穿越或并发写入覆盖 → 越界写文件或结果损坏 | 会话目录始终位于 backend `sessions/` 下；成功上传逐字节一致；reply 为 TTS 原始 WAV | `J5` |

## 判断依据

| J-ID | 判断 | 来源 | 证据或推断 | 状态 |
|---|---|---|---|---|
| J1 | HELLO 的 `last_seq` 表示该会话从 1 开始已连续保存的块号；重复已保存块可幂等 ACK，后续新块只按连续序号推进 | 用户任务 / LLM 推断 | 断线设备按 `last_seq` 跳过块；连续前缀可避免报告最大号时掩盖空洞 | 已确认 |
| J2 | `retry_max_5xx` 表示首次请求之外允许的最大重试次数；timeout、4xx 与连接类失败均直接失败 | 用户任务 / LLM 推断 | 题面用“重试次数上限”描述 5xx，并明确超时和 4xx 不重试；连接失败采用最小副作用策略 | 已确认 |
| J3 | `reply.wav` 保存 TTS 原始 WAV；下行剥离容器后发送 PCM。TTS_END 使用 JSON `{"total_chunks": N, "sha256": "<PCM sha256>"}` | 用户任务 / LLM 推断 | 题面同时要求原样落盘 WAV、设备只播放 PCM、设备可校验完整无缺；下行结束载荷未定义，块计数和内容摘要构成最小可判定完整性契约 | 已确认 |
| J4 | AUDIO_END 成功 ACK 在全部上游调用、两份文件落盘和 PCM 校验完成后发送；随后立即发送下行 | 用户任务 / LLM 推断 | ACK 必须携带 ASR/LLM 结果，且题面规定 ACK 发出后下行；预先校验避免 ACK 成功后才发现无法播放 | 已确认 |
| J5 | `session_id` 只允许由 ASCII 字母、数字、点、下划线和连字符组成，长度 1..128；`device_id` 必须为非空字符串 | 仓库事实 / LLM 推断 | 标识将进入文件路径，白名单防止路径穿越；协议仅声明字段类型，长度与字符集采用最小安全假设 | 已确认 |
| J6 | 上传块 payload 非空、大小不超过 3200，除最后一块外必须等于 3200；AUDIO_END 的 seq、`total_chunks` 与连续块数必须一致 | 外部规范 / LLM 推断 | 音频格式规范规定 3200 字节分块且末块可短，wire 规范规定 seq 语义；一致性规则阻止缺块被摘要偶然掩盖 | 已确认 |

## 建模覆盖声明

| 维度 | 覆盖位置或具体不适用理由 |
|---|---|
| 数据流 | `SC_02`、`SC_07`、`SC_08`、`SC_09` |
| 状态 | `SC_01`、`SC_04`、`SC_10` |
| 时序 | `SC_02`、`SC_06`、`SC_09`、`SC_11` |
| 资源 | `SC_04`、`SC_10`、`SC_11` |
| 不变量 | `影响边界与不变量` |
| 故障 | `SC_03`、`SC_05`、`SC_06`、`SC_11` |

## 验收清单

### 单元测试

- [ ] 流式解码覆盖半包、粘包、流水线帧及 BAD_MAGIC、BAD_CRC、PAYLOAD_TOO_LARGE。
- [ ] 会话覆盖新建、连续块推进、重复块幂等、断线恢复、摘要或块计数失败和安全 session 路径。
- [ ] 上游覆盖正常链、5xx 后成功/耗尽、4xx、timeout 和连接失败的次数与错误码。
- [ ] WAV 校验、PCM 抽取、3200 字节分块及 TTS_END 的 PCM 长度、块数和 sha256 可判定。
- [ ] 两个并发会话分别得到匹配的上传、text、reply 和回复文件。

### Smoke 测试

- [ ] 启动本地假服务和后端，运行仿真设备的 weather 全链路与 time 上传链路；验证 ACK 文本、`upload.wav`、`reply.wav` 和下行 PCM。

### E2E 测试

- 决策：需要
- 依据：目标跨 TCP 设备协议、HTTP 三服务、文件系统和多线程边界，单元测试不能证明真实进程与回环网络链路。
- [ ] 真实启动两个本地进程，使用协议客户端验证成功链、断线续传、并发、故障 ERROR 和断开下行后的服务存活。

## 测试驱动开发

1. `SC_01`、`SC_02`、`SC_03` → 先写会失败的协议与会话单元测试。
2. `SC_04`、`SC_05`、`SC_06` → 先写会失败的续传、完整性和上游故障测试。
3. `SC_07`、`SC_08`、`SC_09` → 先写会失败的编排、音频格式与下行元数据测试。
4. `SC_10`、`SC_11` → 先写会失败的多会话并发和断开隔离测试。
5. 实现满足测试的最小代码，重构后复跑单元、Smoke 和 E2E。

## Scenarios

### Scenario SC_01: 新会话与断点 HELLO

- **GIVEN** 合法的新 `session_id`，或进程内已有从 1 连续保存到 N 的同名会话
- **WHEN** 后端收到合法 HELLO 帧
- **THEN** 返回 seq=0 的 ACK，JSON `last_seq` 分别为 0 或 N，且不同 session 的块状态互不可见
- 测试层：unit
- 依据：用户任务 / `J1`

### Scenario SC_02: 流水线字节流上传

- **GIVEN** HELLO 后，多个顺序 AUDIO_CHUNK 帧以粘包、半包或连续不等待 ACK 的方式到达
- **WHEN** 流式解码器消费任意网络分片
- **THEN** 每帧恰好解析一次，每个块返回同 seq 空载荷 ACK，重组字节顺序与设备原文件一致
- 测试层：unit
- 依据：用户任务

### Scenario SC_03: 非法传输帧关闭当前连接

- **GIVEN** 声明错误魔数、错误 CRC 或超过 262144 的 payload 长度之一的输入
- **WHEN** 后端解析该输入
- **THEN** 分别返回 BAD_MAGIC、BAD_CRC 或 PAYLOAD_TOO_LARGE ERROR，随后关闭当前连接并保留此前会话块
- 测试层：unit
- 依据：用户任务

### Scenario SC_04: 断线后完成全链路

- **GIVEN** 某会话已 ACK 前 N 个连续块后 TCP 断开
- **WHEN** 同一 `session_id` 重连，读取 `last_seq=N` 并上传剩余块及 AUDIO_END
- **THEN** 后端只追加剩余块，生成与完整原文件逐字节一致的 `upload.wav`，并继续完成编排和下行
- 测试层：e2e
- 依据：用户任务 / `J1`

### Scenario SC_05: 上传完整性失败

- **GIVEN** AUDIO_END 的 seq、total_chunks、块形状或 sha256 与连续重组结果不一致
- **WHEN** 后端处理 AUDIO_END
- **THEN** 返回关联 seq 的 INTEGRITY_FAIL ERROR，关闭当前连接，不启动任一上游调用
- 测试层：unit
- 依据：用户任务 / `J6`

### Scenario SC_06: 上游失败在有限时间应答

- **GIVEN** ASR、LLM 或 TTS 任一调用发生 timeout、4xx、单次 5xx 后恢复或持续 5xx
- **WHEN** 后端依序编排服务
- **THEN** timeout 不重试并返回 UPSTREAM_TIMEOUT；4xx 不重试并返回 UPSTREAM_ERROR；5xx 最多重试 `retry_max_5xx` 次，恢复则继续，耗尽则返回 UPSTREAM_ERROR；错误后关闭连接
- 测试层：e2e
- 依据：用户任务 / `J2`

### Scenario SC_07: 成功编排与结果落盘

- **GIVEN** 上传摘要有效且三个假服务返回成功
- **WHEN** 后端处理 AUDIO_END
- **THEN** ASR 接收完整 WAV，LLM 接收 ASR text，TTS 接收 LLM reply；`upload.wav` 等于上传原文，`reply.wav` 等于 TTS 原始响应；AUDIO_END ACK 包含 `ok=true`、text 和 reply
- 测试层：e2e
- 依据：用户任务 / `J4`

### Scenario SC_08: TTS WAV 转设备播放 PCM

- **GIVEN** TTS 返回 PCM 16-bit little-endian、mono、16000 Hz 的合法 WAV
- **WHEN** 后端准备下行
- **THEN** 下行字节仅包含 WAV data chunk 的 PCM，按 3200 字节分块，末块允许短块；格式错误映射 UPSTREAM_ERROR 且不发送成功 ACK
- 测试层：unit
- 依据：用户任务 / `J3`

### Scenario SC_09: ACK 后下行及完整性元数据

- **GIVEN** 成功编排和可播放 PCM 已准备完成
- **WHEN** 后端发送 AUDIO_END ACK
- **THEN** ACK 之后依序发送 seq 从 1 递增的 TTS_CHUNK，最后发送 seq=总块数的 TTS_END；其 JSON total_chunks 与块数一致，sha256 等于完整 PCM 摘要
- 测试层：e2e
- 依据：用户任务 / `J3` / `J4`

### Scenario SC_10: 多设备并发隔离

- **GIVEN** weather 与 time 两个不同 session 同时上传和编排
- **WHEN** 两条 TCP 连接并发完成
- **THEN** 两个会话各自返回匹配的 text/reply，目录内 upload/reply 文件匹配各自素材，无交叉块、文本或音频
- 测试层：e2e
- 依据：用户任务

### Scenario SC_11: 下行断开只终止当前会话发送

- **GIVEN** 一台设备在收到成功 ACK 后、TTS_END 前主动断开，同时另一会话正在处理
- **WHEN** 后端向已断开的连接发送下行帧
- **THEN** 发送异常被当前连接线程吸收，后端进程保持存活，另一会话继续收到完整结果
- 测试层：e2e
- 依据：用户任务
