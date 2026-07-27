# StackChan ESP32-S3 低延迟语音链路系统需求

> spec_version: 2
>
> 状态: 可进入 x-req

## 目标与系统边界

本方案定义一条从 StackChan ESP32-S3 设备到语音服务端的全双工、可取消、可观测语音链路。设备负责唤醒、采集、上行、流式播放与本地抢占；服务端负责会话接入、ASR、TTS、取消传播与恢复协调。方案产物面向后续 x-req，描述系统契约与可验收行为，不包含 task 拆解和实现代码。

范围内：

- StackChan ESP32-S3 上的唤醒词、麦克风采集、音频缓冲、上行传输、扬声器流式播放与播放打断。
- 设备与服务端之间的会话、音频帧、控制事件、心跳、背压、取消、重连与关联标识契约。
- 服务端 ASR、文本交接、TTS 流式生成，以及端到端指标、日志和事件。
- 网络抖动、断网、服务超时、流中断、缓冲压力、重复帧和部分失败的恢复行为。

范围外：

- 对话大模型、知识库、业务回复生成和对话内容策略。本题链路按“ASR 文字直接作为 TTS 输入”的最小闭环建模。
- StackChan 表情、舵机动作及其他具身交互。
- ASR/TTS 供应商选型、固件源文件、部署脚本和开发任务清单。

## 明确假设与待确认项

| ID | 类型 | 内容 | 影响与处理 |
|---|---|---|---|
| A1 | 假设 | 目标 StackChan ESP32-S3 板卡具备可用麦克风、扬声器/功放、I2S/DMA 与 PSRAM；具体引脚、芯片和可用内存由硬件 BOM 确认。 | x-req 需把音频 HAL 与板级配置分离，并在真机验收资源容量。 |
| A2 | 假设 | 首版采用长期保持的 TLS 全双工连接；控制消息与音频二进制帧共享同一逻辑会话。WebSocket、HTTP/2 或自定义 TCP 的最终选型待确认。 | 接口语义保持协议无关；协议选型需满足双向取消、顺序号和背压。 |
| A3 | 假设 | 上行基线为 16 kHz、16-bit、mono、20 ms 帧；下行采样率由 TTS 与设备播放能力协商。PCM 与 Opus 的最终选择待 CPU、带宽和服务端兼容性压测后确认。 | 所有帧携带格式元数据；不得在同一 generation 内无协商切换格式。 |
| A4 | 假设 | ASR 接收流式上行并至少产出 final 文本；TTS 在 final 文本确定后启动并流式回传。ASR partial 仅用于观测或 UI，不触发首版 TTS。 | 保证文本边界明确，避免 partial 修订导致旧语音继续播放。 |
| A5 | 待确认 | 低延迟阈值采用本方案的建议预算：受控网络下 p95“唤醒事件到首个上行音频帧”不高于 200 ms，“说话结束到首个可播放 TTS 样本”不高于 1500 ms；本地打断到静音不高于 100 ms。 | 产品、硬件与服务团队共同确认；确认前以建议预算作为设计和压测基线。 |
| A6 | 待确认 | 唤醒词引擎、ASR/TTS 服务商、语言集合、认证机制、证书轮换方式与数据留存周期。 | 模块通过适配接口隔离供应商；生产发布前必须关闭明文链路并明确留存策略。 |
| A7 | 假设 | 原始音频与完整转写默认不进入普通日志；调试采样需显式授权、限时并脱敏。 | 可观测链路以 ID、时刻、字节数、序号、状态和错误码为主。 |

## 术语与标识

| 术语 | 定义 |
|---|---|
| session_id | 一次设备到服务端的逻辑语音会话标识，可跨短暂传输重连。 |
| generation_id | session 内一次从 listen 到播放结束或取消的交互代次；每次新唤醒单调递增。 |
| transport_epoch | 每次物理连接建立时递增，用于隔离重连前后的帧。 |
| trace_id | 串联设备、网关、ASR、TTS 的分布式追踪标识。 |
| seq | generation 和方向内单调递增的帧序号，用于排序、去重和缺口检测。 |
| barge-in | 用户在 TTS 播放期间通过唤醒词或明确本地输入发起抢占。 |
| stale audio | generation 已取消、已结束、已过期或与当前播放所有者不匹配的下行音频。 |

## 用户要求追溯

| 用户原话要求 | 对应 Requirement | 落实位置 |
|---|---|---|
| 基于 StackChan 与 ESP32-S3 开发板。 | R1 StackChan ESP32-S3 平台约束 | spec.md#requirement-r1-stackchan-esp32-s3-平台约束 |
| 用户通过唤醒词触发 listen。 | R2 唤醒词触发监听 | spec.md#requirement-r2-唤醒词触发监听 |
| 设备采集语音并发送到服务器。 | R3 设备语音采集与上行 | spec.md#requirement-r3-设备语音采集与上行 |
| 服务器完成 ASR 转文字。 | R4 服务端 ASR 转写 | spec.md#requirement-r4-服务端-asr-转写 |
| 服务端根据文字生成 TTS 语音并流式发送回开发板播放。 | R5 TTS 流式回传与设备播放 | spec.md#requirement-r5-tts-流式回传与设备播放 |
| 链路要求低延迟。 | R6 端到端低延迟预算 | spec.md#requirement-r6-端到端低延迟预算 |
| 用户可随时打断播放。 | R7 播放抢占与取消传播 | spec.md#requirement-r7-播放抢占与取消传播 |
| 全过程可观测。 | R8 全链路关联观测 | spec.md#requirement-r8-全链路关联观测 |
| 网络与服务波动下可恢复并稳定运行。 | R9 波动恢复与稳定运行 | spec.md#requirement-r9-波动恢复与稳定运行 |

## 原子需求与验收

### Requirement: R1 StackChan ESP32-S3 平台约束

系统 SHALL 在 StackChan 使用的 ESP32-S3 开发板上承载设备侧语音链路，并通过板级音频抽象访问麦克风、扬声器、I2S/DMA、网络与可用 PSRAM；具体板卡差异不得泄漏到会话和服务端接口。

#### Scenario: 目标板完成语音链路自检

- WHEN 目标固件在确认的 StackChan ESP32-S3 板卡启动并运行上电自检
- THEN 系统报告麦克风、扬声器、I2S/DMA、网络栈和音频缓冲可用，并能进入 `idle`
- 验证: manual

### Requirement: R2 唤醒词触发监听

设备 SHALL 在 `idle` 或 `playing` 状态持续提供本地唤醒检测；有效唤醒事件必须创建新的 generation，并在设备资源就绪后进入 `listening`。播放期间的有效唤醒同时触发 R7 的 barge-in。

#### Scenario: 空闲时唤醒进入监听

- WHEN 设备处于 `idle` 且检测到满足阈值与防抖规则的唤醒词
- THEN 设备创建新的 `generation_id`、记录 `wake_detected` 事件并开始采集语音
- 验证: auto

#### Scenario: 播放时唤醒发起抢占

- WHEN 设备处于 `playing` 且检测到有效唤醒词
- THEN 设备先在本地停止当前播放并标记旧 generation 已取消，再为新 generation 进入 `listening`
- 验证: auto

### Requirement: R3 设备语音采集与上行

设备 SHALL 将麦克风音频按协商格式分帧，通过有界缓冲发送到服务端；每帧必须携带 session、generation、transport epoch、方向和 seq 语义，服务端能够检测重复、乱序与缺口。语音结束必须以明确控制事件封口。

#### Scenario: 连续语音按序上行

- WHEN 设备在 `listening` 状态持续收到麦克风样本且链路可写
- THEN 音频按单调 seq 连续发送，服务端把帧归入唯一 session 和 generation，并在结束事件后停止接收该 generation 的上行音频
- 验证: auto

#### Scenario: 上行背压保持内存有界

- WHEN 服务端消费速度下降并触发发送高水位
- THEN 设备在既定上限内缓冲、暴露背压指标并按恢复策略降级或终止本次 utterance，内存占用保持在资源预算内
- 验证: auto

### Requirement: R4 服务端 ASR 转写

服务端 SHALL 将属于同一有效 generation 的上行语音交给 ASR，并产出带 session、generation 和 trace 关联的 final 文本；取消、过期、格式错误或不完整 generation 的结果不得进入 TTS。

#### Scenario: 有效语音生成唯一 final 文本

- WHEN 服务端收到完整且未取消的 utterance 并由 ASR 成功识别
- THEN 服务端发布一次带关联标识的 `asr_final`，并把该 final 文本交给同 generation 的 TTS
- 验证: auto

#### Scenario: 迟到 ASR 结果被隔离

- WHEN ASR 在 generation 已取消或已过期后返回结果
- THEN 网关丢弃该结果、记录 `stale_result_dropped`，且不创建 TTS 流
- 验证: auto

### Requirement: R5 TTS 流式回传与设备播放

服务端 SHALL 根据有效 final 文本生成 TTS，并在完整语音生成完毕前以有序音频块流式下发；设备在满足当前 generation、格式与序号检查后通过有界抖动缓冲播放，首块达到可播放水位即可开始播放。

#### Scenario: 首个 TTS 块触发播放

- WHEN 设备收到当前 generation 的 `tts_start` 和连续音频块并达到启动水位
- THEN 设备从 `waiting` 进入 `playing`，按序消费音频直至 `tts_end` 且缓冲排空
- 验证: auto

#### Scenario: 旧代次音频被拒绝

- WHEN 设备收到 generation 与当前播放所有者不一致的 TTS 音频块
- THEN 设备丢弃该块、增加 stale-drop 指标且扬声器不输出该块
- 验证: auto

### Requirement: R6 端到端低延迟预算

系统 SHALL 记录统一定义的阶段时间点，并在受控网络基线下满足建议 p95 预算：唤醒到首个上行帧不高于 200 ms、utterance 结束到 ASR final 不高于 800 ms、ASR final 到首个 TTS 下行块不高于 500 ms、utterance 结束到首个可播放样本不高于 1500 ms、本地 barge-in 到静音不高于 100 ms、服务端收到取消不高于本地取消后 300 ms。最终阈值按 A5 确认。

#### Scenario: 受控条件下验证阶段预算

- WHEN 在固定板卡、音频样本、服务配置和定义的受控网络条件下执行至少 100 次完整交互
- THEN 每个阶段输出 p50、p95、p99，建议预算对应的 p95 全部达标，超预算样本可通过 trace_id 定位
- 验证: auto

### Requirement: R7 播放抢占与取消传播

设备 SHALL 允许用户在播放任意时刻发起 barge-in；本地播放必须立即静音并释放旧播放所有权，取消事件必须沿设备、传输、网关、TTS/ASR 传播。已取消 generation 的缓存、在途帧和迟到结果永久失效，任何重连与重试不得恢复其播放。

#### Scenario: 播放中打断永久终止旧音频

- WHEN 用户在 `playing` 状态触发有效 barge-in
- THEN 设备在 100 ms 建议预算内静音、清空旧播放缓冲、递增 generation 并发送幂等取消；服务端停止旧 generation 的生产与下发
- 验证: auto

#### Scenario: 取消后迟到音频保持静默

- WHEN 已取消 generation 的音频在取消、重连或新一轮播放之后到达
- THEN 设备依据 generation fence 丢弃音频，旧音频不进入播放 DMA，观测系统记录丢弃原因
- 验证: auto

### Requirement: R8 全链路关联观测

系统 SHALL 使用 session_id、generation_id、transport_epoch、trace_id 和 seq 关联设备、传输网关、ASR 与 TTS 的结构化事件、日志、指标和追踪；关键状态迁移、阶段时刻、重试、取消、背压、丢弃和故障都必须产生可查询证据。

#### Scenario: 单次交互可端到端还原

- WHEN 运维人员使用任一 trace_id 查询一次已完成、失败或取消的交互
- THEN 能按时间顺序看到唤醒、上行首尾包、ASR 起止、TTS 首尾包、播放起止、状态转换与最终原因，并可计算 R6 的阶段延迟
- 验证: auto

#### Scenario: 日志遵守最小数据原则

- WHEN 系统在默认生产观测配置下记录一次交互
- THEN 常规日志不包含原始音频和完整识别文本，只记录必要关联字段、计数、时刻、状态与错误码
- 验证: auto

### Requirement: R9 波动恢复与稳定运行

系统 SHALL 对断网、重连、心跳超时、ASR/TTS 超时、流中断、重复/乱序帧、缓冲溢出和服务过载采用有界超时、有限退避重试、背压、断路或降级；恢复必须维持 generation fence、幂等取消和资源上限，失败时回到可再次唤醒的确定状态。

#### Scenario: 短暂断网后受控恢复

- WHEN 活跃交互遇到短暂断网且在恢复窗口内重新连通
- THEN 设备建立新的 transport_epoch，双方通过最后确认 seq 协商续传；无法证明连续性时终止当前 generation、释放资源并回到 `idle`
- 验证: auto

#### Scenario: 服务超时有限重试后降级

- WHEN ASR 或 TTS 超过阶段 deadline 或连续返回可重试错误
- THEN 服务端仅在 deadline 与重试预算内指数退避并加入抖动，预算耗尽后终止 generation、发送稳定错误码并释放资源
- 验证: auto

#### Scenario: 长稳运行资源保持有界

- WHEN 在网络抖动、服务慢响应、随机取消与重复帧注入下持续运行 24 小时
- THEN 设备和服务端无资源单调增长、无旧 generation 复播、无取消失效，且每次失败最终进入 `idle` 或可诊断的 `recovering`
- 验证: auto

## Requirement 模块影响

| Requirement | 主要受影响模块 | 验收证据 |
|---|---|---|
| R1 StackChan ESP32-S3 平台约束 | Device Audio & Wake Runtime | 板级自检、真机采播与资源清单 |
| R2 唤醒词触发监听 | Device Audio & Wake Runtime；Device Session & Barge-in Coordinator | 状态迁移事件与唤醒注入测试 |
| R3 设备语音采集与上行 | Device Audio & Wake Runtime；Duplex Voice Transport；Voice Session Gateway | 帧序号、流量、背压和封口事件 |
| R4 服务端 ASR 转写 | Voice Session Gateway；ASR Adapter | ASR trace、final 唯一性和迟到结果丢弃 |
| R5 TTS 流式回传与设备播放 | TTS Adapter & Streamer；Duplex Voice Transport；Device Audio & Wake Runtime | 首块、缓冲水位、播放起止与 stale-drop |
| R6 端到端低延迟预算 | 全部运行时模块；Observability & SLO | 阶段直方图、压测报告与 trace 样本 |
| R7 播放抢占与取消传播 | Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；TTS Adapter & Streamer | 静音延迟、cancel ack、旧帧永不播放 |
| R8 全链路关联观测 | Observability & SLO；所有事件生产模块 | 关联查询、结构化事件和敏感数据审计 |
| R9 波动恢复与稳定运行 | Device Session & Barge-in Coordinator；Duplex Voice Transport；Voice Session Gateway；ASR Adapter；TTS Adapter & Streamer；Observability & SLO | 故障注入、24 小时 soak 与资源水位 |

## 建模覆盖声明

| 元组 | 适用理由 | 落点或不适用理由 | 可验证证据 |
|---|---|---|---|
| 数据流 | 音频与控制跨设备、网络、ASR、TTS 和播放器流动，存在分帧、排序与背压。 | design.md#数据流 | 帧级 trace、seq 连续性、首尾包事件与播放样本 |
| 状态 | 设备与服务端均有可取消、可恢复的会话生命周期。 | design.md#状态模型 | 合法转换测试、非法事件拒绝和终态证据 |
| 时序 | 唤醒、首包、ASR、TTS、首音、取消和 deadline 均有严格先后与预算。 | design.md#时序与延迟预算 | 阶段时间戳、p95 报告与取消时序测试 |
| 资源 | I2S/DMA、音频缓冲、连接、任务、服务配额与播放所有权均需有界管理。 | design.md#资源模型 | 水位指标、资源释放断言和 soak 报告 |
| 不变量 | 旧音频复播和多播放所有者会直接破坏抢占语义。 | design.md#系统不变量 | generation fence、单一所有者断言和 stale 注入测试 |
| 故障 | 网络和语音服务波动是核心运行条件，需覆盖部分失败与恢复。 | design.md#故障恢复 | 断网、超时、乱序、溢出、过载故障注入矩阵 |

## x-req 入口约束

x-req 应保留本包中的 Requirement 名称、Module 名称、关联标识、状态词汇、generation fence 和验收测量口径。后续需求准备可补齐硬件 BOM、协议与编解码选型、供应商能力和生产阈值；任何调整都需更新用户要求追溯、模块覆盖以及 design 中对应的六元组契约。
