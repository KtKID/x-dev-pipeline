# x-spec2 Eval Transcript

## Eval Prompt

请为下面需求创建一个系统级需求包，直接生成可交给 x-req 的方案文档，不进入 task 拆解，不写代码。将不确定项写成明确假设或待确认项。

设计一个基于 StackChan 的 ESP32-S3 开发板语音收发模块。用户通过唤醒词触发 listen；设备采集语音并发送到服务器；服务器完成 ASR 转文字，再根据文字生成 TTS 语音并流式发送回开发板播放。链路要求低延迟、用户可随时打断播放、全过程可观测、网络与服务波动下可恢复并稳定运行。

执行附加约束：`outputs/` 只生成 `spec.md`、`modules.md`、`design.md`；记录本 transcript 与 metrics；使用 `apply_patch` 写文件；运行指定 validator 并修复到成功。

## 已完整读取的 skill、模板与题目

- `skills/x-spec2/SKILL.md`
- `skills/x-spec2/templates/spec.md`
- `skills/x-spec2/templates/modules.md`
- `skills/x-spec2/templates/design.md`
- `skills/x-spec2/evals/stackchan-esp32s3-voice-link.md`

同时只读检查了 `tools/xdev.py` 中 spec2 的包识别、Requirement/Scenario、追溯表、六元组落点、模块回指、状态词汇与 design 引用校验规则。

## 关键执行步骤

1. 将题目拆成 9 条必须保真的原子要求：平台、唤醒、采集上行、ASR、TTS 流式播放、低延迟、播放期打断、全链路观测、波动恢复。
2. 判断数据跨设备/服务端流转，轮次有状态和取消终态，时序决定延迟与 barge-in，I2S/DMA/缓冲有生命周期，弱网和服务失败需要恢复，因此六元组全部适用并生成 `design.md`。
3. 在 `spec.md` 建立 9 个唯一 Requirement、原子 U 追溯、J1–J7 拉式判断依据、六元组理由/落点/验证证据、系统不变量、Q1–Q5 待确认项和可判定 Scenario。
4. 采用可替换的暂定 P95 延迟预算，并固定测量口径：设备内与服务端内使用各自单调时钟；跨端分段附网络条件和时钟同步质量；端到端回复与打断使用同一设备单调时钟。
5. 在 `modules.md` 建立 7 个能力模块及 D1–D7 关键决策唯一真源。每个 D 引用 U/J，保存选择理由、备选与否决原因、重评条件；每个模块回指对应 D。
6. 在 `design.md` 只描述主数据流、消息 envelope、设备/服务端状态机、barge-in 取消顺序、正常时序、超时/重试/重连、资源容量、动态不变量和故障恢复矩阵，并反向引用相关 D。
7. 将“旧音频永不恢复”落实为双端过滤：本地先停 DMA 并清空旧 buffer，递增 `cancel_epoch`；CancelTurn 使用独立控制额度和最高优先级；服务端取消为吸收终态；所有迟到帧同时校验 turn、stream、epoch 与 seq。
8. 使用 `apply_patch` 只写入指定 `with_skill/` 范围，并运行指定 validator。

## 验证命令与实际结果

执行命令：

```bash
python3 tools/xdev.py validate skills/x-spec2-workspace/iteration-1/eval-1/with_skill/run-1/outputs
```

实际退出码：`0`

实际输出：

```text
== skills/x-spec2-workspace/iteration-1/eval-1/with_skill/run-1/outputs  [spec2]
   ok
✓ validate：1 包，0 issue(s)，0 legacy 跳过
```

首轮校验即成功，未发生修复重跑。

## 未决项

- Q1：StackChan ESP32-S3 具体板型、codec、I2S 引脚、RAM/PSRAM、全双工和 AEC 能力。当前方案把播放期持续采集能力设为硬件入口门槛。
- Q2：最终音频编码和双工传输协议。当前基线为上行 16 kHz PCM、下行 24 kHz PCM、TLS WebSocket。
- Q3：产品正式 P95 延迟 SLO 与基准网络。当前包提供可直接执行的暂定阈值和稳定测量口径。
- Q4：ASR/TTS 厂商、真实流式语义、配额、取消与幂等能力。当前方案通过适配器边界隔离供应商差异。
- Q5：设备认证、日志留存、成功采样和文本脱敏策略。当前默认记录元数据并保护原始音频与完整文本。

这些待确认项通过 J 被 Requirement/D 拉式消费；D 的唯一真源位于 modules.md，模块边界与取消/恢复不变量保持稳定。
