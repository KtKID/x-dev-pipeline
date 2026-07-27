# 模块职责、边界与接口

## 模块总览

| 模块 | 状态 | 核心职责 | 回指 Requirement |
|---|---|---|---|
| Device Audio & Wake Runtime | 可进入 x-req | 适配 StackChan ESP32-S3 音频硬件，执行唤醒、采集、分帧、播放与本地音频资源管理。 | R1 StackChan ESP32-S3 平台约束、R2 唤醒词触发监听、R3 设备语音采集与上行、R5 TTS 流式回传与设备播放、R6 端到端低延迟预算、R7 播放抢占与取消传播、R9 波动恢复与稳定运行 |
| Device Session & Barge-in Coordinator | 可进入 x-req | 持有设备会话状态、generation fence、播放所有权和本地抢占顺序，协调恢复。 | R2 唤醒词触发监听、R3 设备语音采集与上行、R5 TTS 流式回传与设备播放、R6 端到端低延迟预算、R7 播放抢占与取消传播、R8 全链路关联观测、R9 波动恢复与稳定运行 |
| Duplex Voice Transport | 可进入 x-req | 提供全双工音频/控制通道、帧序、确认、心跳、背压、取消优先级与重连 epoch。 | R3 设备语音采集与上行、R5 TTS 流式回传与设备播放、R6 端到端低延迟预算、R7 播放抢占与取消传播、R8 全链路关联观测、R9 波动恢复与稳定运行 |
| Voice Session Gateway | 可进入 x-req | 鉴权和接入设备会话，校验帧与状态，编排 ASR/TTS，执行 deadline、取消和恢复协商。 | R3 设备语音采集与上行、R4 服务端 ASR 转写、R5 TTS 流式回传与设备播放、R6 端到端低延迟预算、R7 播放抢占与取消传播、R8 全链路关联观测、R9 波动恢复与稳定运行 |
| ASR Adapter | 可进入 x-req | 隔离 ASR 供应商，接收流式音频，输出 partial/final，执行超时、取消和结果 fencing。 | R4 服务端 ASR 转写、R6 端到端低延迟预算、R7 播放抢占与取消传播、R8 全链路关联观测、R9 波动恢复与稳定运行 |
| TTS Adapter & Streamer | 可进入 x-req | 隔离 TTS 供应商，把 final 文本转换为有序音频块，支持首块流式返回、背压和取消。 | R5 TTS 流式回传与设备播放、R6 端到端低延迟预算、R7 播放抢占与取消传播、R8 全链路关联观测、R9 波动恢复与稳定运行 |
| Observability & SLO | 可进入 x-req | 统一结构化事件、指标、追踪、错误码和 SLO 计算，执行敏感数据最小化。 | R6 端到端低延迟预算、R8 全链路关联观测、R9 波动恢复与稳定运行 |

## 模块边界与所有权

| 模块 | 独占所有权 | 输入 | 输出 | 明确边界 |
|---|---|---|---|---|
| Device Audio & Wake Runtime | 麦克风/扬声器 I2S 与 DMA、采集环形缓冲、播放抖动缓冲、唤醒引擎实例 | 硬件样本、播放块、start/stop 命令 | wake 事件、上行音频帧、播放水位和音频故障 | 不决定服务端 session 生命周期，不接受未通过 generation fence 的播放数据。 |
| Device Session & Barge-in Coordinator | 当前 session/generation/transport_epoch、设备状态机、播放 owner token | wake、utterance end、传输事件、播放事件、用户取消 | 状态转换、generation 变更、cancel、资源 acquire/release | 不直接驱动 I2S，不实现网络协议与 ASR/TTS。 |
| Duplex Voice Transport | 物理连接、方向序号、确认游标、发送队列、心跳与重连计时器 | 音频帧、控制事件、网络字节 | 已验证的远端事件、ack、背压和连接状态 | 不修改业务 generation，不在未获协调器授权时重放音频。 |
| Voice Session Gateway | 服务端 session registry、generation cancellation token、阶段 deadline、服务编排上下文 | 客户端事件、ASR/TTS 回调、鉴权结果 | ASR/TTS 请求、下行控制/音频、取消 ack、稳定错误 | 不持有设备硬件资源，不绕过 generation 校验转发供应商结果。 |
| ASR Adapter | 单 generation ASR 流与供应商请求句柄 | 已验证的上行音频、utterance end、cancel | partial/final、错误、阶段指标 | 不启动 TTS，不把迟到结果直接发送给设备。 |
| TTS Adapter & Streamer | 单 generation TTS 请求句柄、下行块序号和供应商读取缓冲 | final 文本、格式参数、cancel、下游 credit | tts_start、音频块、tts_end、错误 | 不拥有设备播放状态，取消后停止生产并让未发送块失效。 |
| Observability & SLO | 指标定义、事件 schema、trace/span 关联和告警规则 | 各模块事件与指标 | trace、日志、聚合指标、SLO 与告警 | 不接触实时控制路径，不默认存储原始音频和完整文本。 |

## 外部依赖

| 依赖 | 使用方 | 必要能力 | 失败隔离 |
|---|---|---|---|
| StackChan ESP32-S3 板级 BSP/HAL | Device Audio & Wake Runtime | I2S 全双工或可切换采播、DMA、时钟、PSRAM、Wi-Fi/TLS | 启动自检失败进入可诊断不可服务状态；运行时音频故障释放 DMA 后回到 idle/recovering。 |
| 唤醒词引擎 | Device Audio & Wake Runtime | 本地低功耗连续检测、阈值与防抖 | 引擎异常只影响新唤醒，现有 session 资源可被协调器回收。 |
| 网络与时间源 | Duplex Voice Transport；Observability & SLO | TLS、双向流、单调时钟；可选 wall clock 同步 | 延迟以单机单调时钟和跨节点 span 组合计算，时钟漂移单独监测。 |
| ASR 服务 | ASR Adapter | 流式输入、final 输出、cancel 或客户端主动断流 | deadline、有限重试、断路器与供应商错误映射。 |
| TTS 服务 | TTS Adapter & Streamer | 流式首块、格式协商、cancel 或客户端主动断流 | deadline、背压、有限重试；首块已播放后禁止无缝切换为另一语音。 |
| 指标/日志/追踪后端 | Observability & SLO | 结构化摄取、trace 检索、直方图和告警 | 遥测发送有界且异步；后端故障不得阻塞实时音频路径。 |

## 接口与事件契约

### 通用信封

每个控制事件和逻辑音频帧必须具有以下语义字段；二进制协议可用固定头编码，字段语义保持一致。

| 字段 | 必填范围 | 语义与约束 |
|---|---|---|
| protocol_version | 全部 | 协议主/次版本；不兼容主版本在 session 建立阶段拒绝。 |
| session_id | session 建立后全部 | 服务端确认的逻辑会话；设备重启后新建。 |
| generation_id | generation 内全部 | 单 session 单调递增；取消或新唤醒形成 fence。 |
| transport_epoch | 传输消息全部 | 每次物理重连递增；旧 epoch 的确认不得推进新 epoch 游标。 |
| trace_id | generation 内全部 | 贯通设备、网关、ASR、TTS；服务端可补齐 span_id。 |
| direction | 音频帧 | `uplink` 或 `downlink`，每方向独立 seq。 |
| seq | 音频帧 | generation+direction 内单调递增；接收端去重并检测缺口。 |
| monotonic_ts | 设备/服务事件 | 发出方单调时间，用于本节点阶段耗时。 |
| type | 控制事件 | 稳定事件类型。 |
| payload/format | 按类型 | 音频格式、字节数、错误码或阶段数据；有严格大小上限。 |

### 设备到服务端

| 事件 | 发送前置条件 | 服务端行为 | 幂等键 |
|---|---|---|---|
| `session_start` | 已鉴权连接，设备无已确认 session 或需新建 | 协商协议、音频格式、容量、heartbeat，返回 session_ack | device_id + client_session_nonce |
| `listen_start` | 新 generation 已创建 | 创建 generation 上下文和 ASR 流，拒绝小于等于 cancelled fence 的 generation | session_id + generation_id |
| `audio_chunk` | listening/uploading 且未取消 | 按 seq 去重、排序窗口检查、喂入 ASR，按 credit 回 ack | session_id + generation_id + direction + seq |
| `utterance_end` | 本地 VAD/超时/用户结束 | 封口 ASR 输入，禁止后续新上行帧，等待 final | session_id + generation_id |
| `cancel` | barge-in、用户取消或本地终止 | 立即提升 cancelled fence，取消 ASR/TTS/下行队列并返回 cancel_ack | session_id + generation_id |
| `heartbeat` | 连接活跃 | 回报 ack 游标、当前 generation 和容量 | transport_epoch + heartbeat_seq |

`cancel` 控制帧使用独立优先队列或保留 credit，避免被音频背压阻塞。

### 服务端到设备

| 事件 | 发送前置条件 | 设备行为 | 有效性检查 |
|---|---|---|---|
| `session_ack` | session 协商成功 | 保存 session_id、格式与容量，进入 idle | client nonce 和 transport_epoch 匹配 |
| `asr_partial` | 供应商提供且 generation 有效 | 仅记录可选进度，不驱动播放 | generation 等于当前且未取消 |
| `asr_final` | final 唯一且 generation 有效 | 记录阶段时间；等待 TTS | 同 generation 只接受首个 final |
| `tts_start` | TTS 格式已确定 | 校验格式，创建空播放缓冲，保持 waiting | generation 等于当前 owner 候选 |
| `tts_audio` | TTS 流有效且持有 credit | 按 seq 进入抖动缓冲，达到水位后播放 | generation/epoch/seq/格式均有效 |
| `tts_end` | 供应商正常完成 | 缓冲排空后释放播放 owner，进入 idle | end seq 不小于已接收最大 seq |
| `cancel_ack` | 服务端完成 fence 提升 | 结束取消等待；不得改变本地已静音事实 | session/generation 与取消请求匹配 |
| `error` | generation 或 session 失败 | 按稳定错误码决定 idle/recovering/重建 session | scope、retryable、deadline 明确 |
| `heartbeat_ack` | heartbeat 有效 | 更新连接存活、ack 游标和 credit | transport_epoch 匹配 |

## 状态词汇与状态所有权

| 状态 | 权威所有者 | 进入条件 | 退出条件 |
|---|---|---|---|
| idle | Device Session & Barge-in Coordinator | session 可用且无活跃 generation | 有效 wake 或连接故障 |
| listening | Device Session & Barge-in Coordinator | 新 generation 建立、麦克风已获取 | utterance_end、cancel 或采集故障 |
| uploading | Device Session & Barge-in Coordinator | 音频持续发送；可与 listening 重叠的实现子态 | utterance_end、cancel 或链路失败 |
| waiting | Device Session & Barge-in Coordinator | 上行封口，等待 ASR/TTS 首块 | tts_start/首块、cancel、deadline 或故障 |
| playing | Device Session & Barge-in Coordinator | 当前 generation 获取唯一 playback owner 且达到启动水位 | tts_end 排空、barge-in 或播放故障 |
| interrupted | Device Session & Barge-in Coordinator | 本地 fence 已提升、旧播放已静音 | 本地资源清理完成后进入 listening 或 idle |
| recovering | Device Session & Barge-in Coordinator | 连接/服务/音频资源暂不可用且仍有恢复预算 | session 恢复进入 idle，或预算耗尽进入可诊断 idle/不可服务状态 |
| receiving_asr | Voice Session Gateway | listen_start 有效并创建 ASR 流 | final、cancel、deadline 或 ASR 错误 |
| synthesizing | Voice Session Gateway | ASR final 有效并创建 TTS 流 | tts_end、cancel、deadline 或 TTS 错误 |
| cancelled | Voice Session Gateway | cancel 或更高 generation 形成 fence | 仅释放资源；该 generation 不得重新激活 |
| completed | Voice Session Gateway | TTS 正常结束且下行完成 | 终态；仅清理资源 |
| failed | Voice Session Gateway | 不可恢复错误或预算耗尽 | 终态；仅清理资源并发送错误 |

设备状态的唯一写者是 Device Session & Barge-in Coordinator。服务端 generation 状态的唯一写者是 Voice Session Gateway。其他模块通过事件请求转换，禁止自行修改权威状态。

## Requirement 到模块覆盖

| Requirement | 承接模块 |
|---|---|
| R1 StackChan ESP32-S3 平台约束 | Device Audio & Wake Runtime |
| R2 唤醒词触发监听 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator |
| R3 设备语音采集与上行 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway |
| R4 服务端 ASR 转写 | Voice Session Gateway；ASR Adapter |
| R5 TTS 流式回传与设备播放 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；TTS Adapter & Streamer |
| R6 端到端低延迟预算 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；ASR Adapter；TTS Adapter & Streamer；Observability & SLO |
| R7 播放抢占与取消传播 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；ASR Adapter；TTS Adapter & Streamer |
| R8 全链路关联观测 | Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；ASR Adapter；TTS Adapter & Streamer；Observability & SLO |
| R9 波动恢复与稳定运行 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；ASR Adapter；TTS Adapter & Streamer；Observability & SLO |

## 跨模块契约约束

- 所有生成和消费音频的模块共同使用 session_id + generation_id + direction + seq 判定身份；transport_epoch 只描述物理连接代次。
- Device Session & Barge-in Coordinator 在本地先完成静音和 fence，再把 cancel 交给 Duplex Voice Transport；远端确认用于观测和资源收敛。
- Voice Session Gateway 在调用 ASR Adapter、TTS Adapter & Streamer 以及发送任何下行数据前检查 cancelled fence。
- Duplex Voice Transport 只重传仍然有效且已获 ack/credit 契约允许的帧；连接恢复无法证明连续性时通知协调器终止 generation。
- Observability & SLO 的遥测队列有独立容量和丢弃策略，实时音频与 cancel 控制优先于遥测。
