# 动态模型

## 数据流

关联决策：`D1`、`D3`、`D4`、`D5`、`D6`、`D7`。

### 主链路

1. `设备音频运行时` 持续向唤醒检测扇出麦克风样本；`交互会话协调器` 接受 `WakeEvent` 后生成 `session_id`、`turn_id`、`trace_id` 和当前 `cancel_epoch`，落实 `唤醒进入监听`。
2. `设备音频运行时` 将活动轮次语音按 20 ms 帧化，`设备双工传输` 增加 `stream_id`、`seq`、格式和采集时间戳，经持久连接发送到 `服务端语音网关`，落实 `音频采集与上行`。
3. `服务端语音网关` 校验关联标识、epoch、序号和格式，去重后推进累计确认游标，同时把有序音频写入 `ASR 适配器`。
4. `ASR 适配器` 在 utterance end 后交付唯一 final text 引用；网关再次检查轮次终态，再把有效文本交给 `TTS 适配器`，落实 `服务端语音识别`。
5. `TTS 适配器` 先交付格式声明和首个音频块，再持续交付后续块；网关分配独立下行 `stream_id` 和序号，经发送窗口流式下发，落实 `流式合成与播放`。
6. `设备双工传输` 验证下行轮次、epoch 和序号，把当前有效块写入 `设备音频运行时` 的抖动缓冲；达到启动水位后，唯一播放器 owner 获取扬声器租约并播放。
7. 每个边界动作向 `端到端遥测` 发送同一关联链上的状态、时间戳、序号、水位、错误和资源事件，落实 `端到端可观测` 与 `可测量低延迟`。

### 核心消息契约

| 消息 | 必需字段 | 生产者 → 消费者 | 一致性规则 |
|---|---|---|---|
| `OpenTurn` | protocol_version、device_id、connection_id、session_id、turn_id、trace_id、cancel_epoch、audio_format | 交互会话协调器 → 服务端语音网关 | `turn_id` 单设备唯一；同一幂等键重复打开只返回当前状态 |
| `AudioFrame` | session_id、turn_id、stream_id、cancel_epoch、seq、captured_monotonic_ms、duration_ms、format、payload | 设备音频运行时/设备双工传输 → 服务端语音网关 | stream 内 seq 单调；重复去重；格式在 stream 内固定 |
| `EndOfUtterance` | turn_id、stream_id、cancel_epoch、last_seq、reason、device_monotonic_ms | 设备双工传输 → 服务端语音网关 | 只有最高连续确认达到 last_seq 后才结束 ASR 输入 |
| `AsrFinal` | turn_id、trace_id、text_ref、provider_request_id、server_monotonic_ms | ASR 适配器 → 服务端语音网关 | 每轮最多一个 final；终态后只记录 late-drop |
| `TtsAudioFrame` | turn_id、stream_id、cancel_epoch、seq、duration_ms、format、payload | TTS 适配器/服务端语音网关 → 设备双工传输 | 设备仅接收 current turn/current epoch；乱序窗口有界 |
| `CancelTurn` | session_id、turn_id、cancel_epoch、reason、device_monotonic_ms | 交互会话协调器 → 服务端语音网关/适配器 | 控制优先；幂等；更大 epoch 覆盖更小 epoch；取消是终态 |
| `Ack` | direction、turn_id、stream_id、highest_contiguous_seq、window_remaining | 双向 | 累计确认只前进；重连从确认游标恢复 |
| `VoiceEvent` | 全部关联标识、module、event、state、reason、monotonic_ts、wall_ts、clock_quality、attrs | 所有模块 → 端到端遥测 | 默认 attrs 仅含元数据；音频和完整文本不入日志 |

上行 PCM 基线每帧 640 bytes、约 32 KB/s；下行 PCM 基线约 48 KB/s。Q2 若选择压缩编码，消息 envelope、序号、取消与确认语义保持不变。

## 状态流转

关联决策：`D2`、`D4`。

### 设备轮次状态

状态事实源是 `交互会话协调器`。

| 状态 | 含义 | 合法入口 | 合法出口 |
|---|---|---|---|
| `Idle` | 无活动轮次，唤醒检测可用 | 启动完成、Completed、Failed 资源释放完成 | WakeAccepted → `Listening`；连接不可用 → `Recovering` |
| `Listening` | 新轮次已创建，采集启动，等待有效语音 | `Idle` 唤醒；`Playing` barge-in 完成本地取消 | 首个语音帧 → `StreamingUp`；取消/超时 → `Interrupted`；断网 → `Recovering` |
| `StreamingUp` | 采集与上传并行，等待 utterance end | `Listening` 首帧 | utterance end → `WaitingAsr`；取消 → `Interrupted`；断网 → `Recovering` |
| `WaitingAsr` | 上行结束，等待 final text | `StreamingUp` utterance end | final text → `WaitingTts`；超时/失败 → `Recovering` 或 `Idle`；取消 → `Interrupted` |
| `WaitingTts` | final text 有效，等待 TTS 首块 | `WaitingAsr` final text | 首块有效 → `Playing`；超时/失败 → `Recovering` 或 `Idle`；取消 → `Interrupted` |
| `Playing` | 当前 stream 持有扬声器租约并消费下行 | `WaitingTts` 首块达到启动水位 | stream end → `Idle`；barge-in → `Interrupted`；流中断 → `Recovering` |
| `Interrupted` | 本地取消已生效、旧资源正在释放的瞬态终态 | 任一活动态收到 barge-in/本地取消 | 有新唤醒 → 新轮次 `Listening`；无新轮次且释放完成 → `Idle` |
| `Recovering` | 连接或服务不可用，按策略重连/收敛当前轮次 | 断网、服务超时、流中断、背压故障 | 上行短断且游标有效 → `StreamingUp`；连接恢复且当前轮次已终止 → `Idle`；持续失败 → 保持 `Recovering` |

`Interrupted` 只描述被取消旧轮次的终态。barge-in 可以在同一原子处理内让旧轮次进入 `Interrupted`，随后用新 `turn_id` 创建 `Listening`；两者通过 turn 标识区分。

### 服务端轮次状态

状态事实源是 `服务端语音网关`，单 connection owner 串行化更新。

`Accepted → Receiving → Recognizing → Synthesizing → StreamingDown → Completed`

任一非终态可进入 `Canceled` 或 `Failed`。`Completed`、`Canceled`、`Failed` 均为吸收终态；供应商迟到回调、重连旧队列和重复控制消息只能增加观测计数，不能改变终态。

### 重连状态对账

- 设备发送 `Resume(connection_id, current_turn_id, cancel_epoch, uplink_ack, downlink_ack)`；网关返回 `resumable` 与双向确认游标。
- `StreamingUp` 且断连不超过 3 秒、网关仍持有有效 turn 时，设备仅重传未确认帧并继续采集缓冲；超过时限、session 丢失或缓冲缺口使轮次进入取消/失败终态。
- `Playing` 发生断连时立即停止播放并清空下行缓冲。连接恢复后旧 TTS 不续播，设备回到 `Idle`；这条规则消除长静音后的突发旧语音。
- 服务端收到比本地更新的 `cancel_epoch` 时立即提升终态；设备收到更旧 epoch 的任何状态或音频时丢弃。

## 时序

关联决策：`D2`、`D3`、`D4`。

### 正常交互

1. 唤醒检测发出 `WakeEvent`，协调器创建轮次并记录 `wake_accepted`。
2. 音频运行时启动活动采集；传输可在首帧后立即发送，无需等待整段语音。
3. 网关边收边确认并把连续帧写入 ASR；设备 VAD/端点检测发送 utterance end。
4. ASR final 到达后，网关进行终态检查并立即启动 TTS。
5. TTS 首块经网关直接下发；设备达到暂定 60–120 ms 启动水位便开始播放，同时继续接收后续块。
6. TTS 结束标记到达且缓冲排空后，设备释放扬声器，双方把轮次标记完成。

### barge-in 取消顺序

1. `Playing` 期间唤醒检测保持工作并发出 barge-in。
2. 协调器在单个临界区内把旧 turn 标记 `Interrupted`、递增 `cancel_epoch` 并撤销播放租约。
3. 音频运行时立即静音、停止旧 DMA 链、清空旧 downlink buffer；这一步不等待网络。
4. 传输把 `CancelTurn` 插入最高优先级控制队列，并清除本地旧 turn 待发音频。
5. 协调器生成新 `turn_id` 并进入 `Listening`；传输保证 CancelTurn 先于新 turn 的音频出队。
6. 网关先把旧 turn 写入 `Canceled`，再调用 ASR/TTS cancel handle、清空发送窗口并返回 `CancelAck`。
7. 任意迟到供应商回调或网络音频在网关和设备两端都经过终态/epoch 检查并丢弃。

以上顺序落实 `播放期打断`：本地静音 P95 不高于 200 ms，健康网络下 CancelAck 目标 P95 不高于 500 ms；新轮次采集不依赖 CancelAck。

### 暂定延迟预算与口径

| 分段 | 起点 → 终点 | 时钟口径 | P95 暂定预算 |
|---|---|---|---|
| 唤醒响应 | `wake_accepted` → 首采集帧 ready | 同一设备单调时钟 | ≤ 100 ms |
| 上行首包 | 首采集帧 ready → 网关首帧 receive | 两端事件关联；报告时钟同步质量与网络 RTT | ≤ 250 ms |
| ASR 收敛 | 网关 receive EOU → ASR final callback | 同一服务端单调时钟 | ≤ 800 ms |
| TTS 首块到端 | ASR final callback → 设备首 TTS 块 receive | 两端事件关联；报告时钟同步质量与网络 RTT | ≤ 700 ms |
| 播放启动 | 设备首 TTS 块 receive → audible start | 同一设备单调时钟 | ≤ 120 ms |
| 端到端回复 | 设备 utterance end → audible start | 同一设备单调时钟 | ≤ 1800 ms |
| 打断静音 | barge-in accepted → speaker silent | 同一设备单调时钟 | ≤ 200 ms |

正式值属于 Q3。验收至少采集 100 个成功轮次，固定板型/固件/服务版本和参考网络，同时报告 P50、P95、P99、失败样本、RTT/丢包和时钟质量；`端到端遥测` 保存原始事件以便复算。

### 超时、重试与优先级

- 控制队列优先级：`CancelTurn`、连接关闭/错误、确认/窗口更新、轮次控制、音频数据、遥测批次。
- ASR 在网关收到 EOU 后 3 秒无 final 即超时；TTS 首块等待 3 秒、块间隔 1 秒即超时。这些值随 Q4/Q3 可配置。
- 只有幂等键稳定、供应商标记 retryable 且 TTS 尚未产生首块时，服务调用才可最多重试一次；已播放任何音频后的服务失败直接终止轮次。
- 重连从 0.5 秒退避到 1、2、4、8、16、30 秒，加入正负 20% 随机抖动；连接稳定 60 秒后重置退避。
- 心跳连续两个周期无响应即判定连接失效；周期默认 5 秒。语音活动期间仍由音频 ack/超时提供更快故障检测。

## 资源

关联决策：`D1`、`D3`、`D7`。

| 资源 | 唯一 owner | 暂定容量/配额 | 获取与释放 | 压力行为与证据 |
|---|---|---|---|---|
| 麦克风与 I2S RX | 设备音频运行时 | 一个物理采集器；唤醒检测和活动轮次使用只读扇出 | 启动时获取；设备关机/音频故障时释放；轮次只增减订阅 | 慢订阅者不得阻塞 I2S；丢弃并上报 subscriber lag/overrun |
| 扬声器与 I2S TX/DMA | 设备音频运行时 | 一个播放租约；仅 current turn/current epoch | 首块达到水位时获取；完成、取消、断网、underrun 超限时释放 | 租约冲突拒绝；取消清 DMA；上报 owner、descriptor 和 silent latency |
| 上行环形缓冲 | 设备音频运行时 | PCM 基线 2 秒，约 64 KB；Q1/Q2 可调整 | `Listening` 创建，EOU 确认或终态释放 | 高水位通知传输；满时终止当前轮次并产生 `uplink_overrun`，禁止无限扩容 |
| 下行抖动缓冲 | 设备音频运行时 | PCM 基线 500 ms，约 24 KB；启动水位 60–120 ms | 有效 TTS stream 创建，完成/取消/流中断释放 | 高水位通过接收窗口施加背压；underrun 超阈值终止流，旧块不填充新流 |
| 双工连接与发送窗口 | 设备双工传输/服务端语音网关各自拥有本端 | 每设备一连接；每方向窗口按字节和帧双重限制 | 设备联网获取；断开清理并进入退避；resume 重建游标 | 窗口为零暂停数据帧，CancelTurn 保留独立控制额度；上报 inflight、高水位、重传 |
| 设备音频/网络任务 | 对应设备模块 | 固定任务数、固定栈和固定优先级 | 启动创建；停机或不可恢复故障释放 | 30 分钟故障测试检查任务数、stack watermark 和 heap 趋势 |
| 服务端 turn 与适配器调用 | 服务端语音网关 | 每设备一个活动 turn；全局/租户并发由配置限制 | OpenTurn 获取；Completed/Canceled/Failed 释放 | 配额不足快速失败；终态 cancel handle；上报 active turns、queue 和 circuit state |
| 设备遥测队列 | 端到端遥测 | 固定事件数/字节；错误与终态高优先级 | 启动创建；批量上传后复用 | 满时按优先级淘汰低价值成功采样，保留错误/取消/资源释放计数并上报 dropped events |

容量默认值必须在 Q1 确认后通过静态内存预算和目标板 HIL 校验。任何资源申请失败都返回结构化错误，驱动当前轮次进入可收敛终态。

## 动态不变量

关联决策：`D1`、`D2`、`D3`、`D4`。

- `设备音频运行时` 是物理 I2S/DMA 的唯一 owner，`交互会话协调器` 是设备轮次状态与 `cancel_epoch` 的唯一 owner，`服务端语音网关` 是服务端 turn 终态的唯一 owner。
- 任一到达播放器的帧必须同时满足 `turn_id == current_turn_id`、`cancel_epoch == accepted_epoch`、`stream_id == current_stream_id`、序号位于当前接收窗口。
- `Canceled`、`Interrupted`、`Completed`、`Failed` 对所属 turn 均不可逆；重试、resume 和供应商回调只能在同一终态下返回幂等结果或 late-drop。
- CancelTurn 的发送额度和处理优先级独立于音频数据窗口；数据背压不能阻挡取消。
- 新 turn 可在旧 turn 等待 CancelAck 时开始采集；扬声器租约和播放器过滤保证旧 turn 无法与新 turn 同时发声。
- 所有队列容量、重试次数、重排窗口、服务超时和退避上限均可枚举且可观测；故障不能产生无界任务、连接或内存增长。
- 每个终态事件必须包含 reason、最后确认序号、缓冲高水位、资源释放 snapshot 和关联标识，支持 `端到端可观测` 的轮次重建。

属性测试应随机生成唤醒、帧、重复/乱序、取消、CancelAck、断连、resume 和供应商迟到回调，持续断言以上不变量与 `播放期打断` 的旧音频失效规则。

## 故障与恢复

关联决策：`D1`、`D2`、`D3`、`D4`、`D5`、`D6`、`D7`。

| 失败入口 | 检测 | 当前轮次处理 | 恢复路径 | 可观测证据 |
|---|---|---|---|---|
| 唤醒误触/重复事件 | 唤醒事件 debounce 与当前状态 | 同一窗口只接受一次；`Playing` 时按 barge-in 处理 | 保持当前或创建唯一新 turn | wake accepted/rejected reason、模型分数、turn count |
| 上行短时断网 | ack 停滞、socket 错误、心跳 | 进入 `Recovering`，最多保留 2 秒音频；3 秒内 session 有效则从 ack 游标续传 | 带抖动退避重连；去重恢复 ASR 输入 | disconnect duration、resume result、retransmit frames、buffer high-water |
| 长时断网/session 丢失 | 断连超过 3 秒或 resume rejected | 取消当前 turn，清音频缓冲和租约 | 在退避上限持续尝试连接；连接恢复后回 `Idle` 等待新唤醒 | terminal reason、cancel epoch、resource snapshot、reconnect attempts |
| ASR 超时/5xx/限流 | EOU 后 3 秒无进展或适配器错误 | 首个 final 前满足幂等条件时重试一次；随后 `Failed` | 断路器冷却后允许新 turn；当前 turn 释放 | provider request ID、retry eligibility、timeout、circuit state |
| TTS 首块超时 | ASR final 后 3 秒无首块 | 首块产生前满足幂等条件时重试一次；随后 `Failed` | 释放适配器和扬声器预留，设备回可唤醒状态 | first-byte latency、retry、terminal reason |
| TTS 中途断流/块间超时 | 1 秒无块、stream error、序号缺口超窗口 | 立即停播并清缓冲，取消服务调用；当前 turn 失败且不拼接新流 | 新唤醒创建新 turn | last seq、underrun/gap、speaker silent、late-drop |
| 设备上行缓冲溢出 | high-water 与写失败 | 停止采集并结束当前 turn，发送错误或取消 | 释放缓冲，网络恢复后新 turn | capacity、high-water、dropped duration、heap snapshot |
| 下行缓冲溢出 | 接收窗口为零后仍收到数据或本地写失败 | 终止当前 TTS stream，停止播放 | 清缓冲并回 `Idle`，网关记录协议/背压失败 | advertised window、bytes overrun、stream terminal、resource snapshot |
| 播放期 barge-in | WakeEvent/物理 stop | 本地先静音、递增 epoch、清旧资源，CancelTurn 高优先传播 | 立即开始新 `Listening`；旧 turn 维持取消终态 | silent latency、cancel send/ack latency、late audio drop |
| 遥测上传失败 | sink/网络错误、队列高水位 | 语音主链路继续；错误/终态事件优先保留，成功采样可淘汰 | 连接恢复后批量上传当前保留事件 | telemetry dropped by priority、queue high-water、oldest age |

### 部分失败与收敛规则

- 设备本地取消成功而服务端暂时离线：设备取消已经生效；CancelTurn 保留在独立控制槽，resume 后发送，服务端通过更高 epoch 收敛。
- 服务端取消成功而 CancelAck 丢失：设备本地终态保持；重复 CancelTurn 得到幂等 CancelAck。
- ASR 已产出文本而 TTS 失败：文本只作为轮次内部引用保留到终态，当前轮次失败并释放；下一轮重新采集，避免复用过期文本。
- TTS 已生成块而设备断网：网关发送窗口有界；超过 resume 窗口便取消 TTS。设备重连后旧播放不续播。
- 观测 sink 故障：语音控制路径保持独立；设备队列按优先级有界淘汰，并至少保留聚合丢弃计数和资源释放终态。

### 稳定性判据

在 30 分钟故障注入中循环断网、5xx、限流、超时、乱序、重复、缓冲压力和 barge-in；恢复正常网络与服务后，新健康轮次必须成功。设备任务数、连接数、DMA 描述符、I2S owner 和堆内存趋势保持在基线容差内，服务端 active turn、适配器调用和发送队列回落到基线，所有旧 turn 保持终态且无音频复活。这一判据落实 `波动恢复与稳定运行`。
