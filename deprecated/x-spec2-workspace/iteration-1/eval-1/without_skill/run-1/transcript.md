# 无 skill 基线执行记录

## Eval Prompt

请为下面需求创建一个系统级需求包，直接生成可交给 x-req 的方案文档，不进入 task 拆解，不写代码。将不确定项写成明确假设或待确认项。

设计一个基于 StackChan 的 ESP32-S3 开发板语音收发模块。用户通过唤醒词触发 listen；设备采集语音并发送到服务器；服务器完成 ASR 转文字，再根据文字生成 TTS 语音并流式发送回开发板播放。链路要求低延迟、用户可随时打断播放、全过程可观测、网络与服务波动下可恢复并稳定运行。

## 读取的测试材料

- `skills/x-spec2/evals/stackchan-esp32s3-voice-link.md`：完整测试题、预期三件产物、必须保真的九项要求、六元组覆盖预期和验收判定。
- `tools/xdev.py`：仅阅读包类型识别与 V2/V3/V13–V17 机械校验契约，用于确认标记、Requirement/Scenario、追溯表、模块表、建模落点和 design 引用规则。
- 未读取 `skills/x-spec2/SKILL.md`。
- 未读取 `skills/x-spec2/templates/` 下的任何文件。

## 关键执行步骤

1. 从测试题提取九条用户要求，建立一对一 Requirement 名称与用户原话追溯。
2. 将系统边界划分为设备音频、设备会话、双工传输、服务端网关、ASR、TTS、观测七个模块，建立 Requirement 到 Module 与 Module 到 Requirement 双向覆盖。
3. 在 `design.md` 集中设计数据流、状态、时序、资源、不变量和故障六元组，加入 generation fence、播放单一所有者、取消优先通道、背压与有界恢复。
4. 把硬件、协议、音频格式、延迟阈值、供应商、安全和隐私中的不确定项登记为假设或待确认决策。
5. 仅在 `outputs/` 写入 `spec.md`、`modules.md`、`design.md`；未创建 task、README、checklist 或代码。

## 验证命令和实际结果

命令：

```text
python3 tools/xdev.py validate skills/x-spec2-workspace/iteration-1/stackchan-esp32s3-voice-link/without_skill/outputs --json
```

实际结果：退出码 `0`；包类型为 `spec2`；`skipped: false`；`total_issues: 0`；`issues: []`。

最终结构核对命令：

```text
find skills/x-spec2-workspace/iteration-1/stackchan-esp32s3-voice-link/without_skill/outputs -maxdepth 1 -type f -print | sort
```

预期并最终确认仅包含 `design.md`、`modules.md`、`spec.md`。字符统计使用 `wc -m`，实际值记录在 `metrics.json`。

## 未决项

- 目标 StackChan ESP32-S3 板型、麦克风/功放/扬声器器件、I2S 引脚与可用 PSRAM。
- 全双工传输协议、设备认证与证书轮换方式。
- 上下行编解码、采样率、帧长、缓冲容量与回声消除能力。
- 唤醒词引擎、VAD 策略、ASR/TTS 服务商、语言与供应商取消能力。
- 建议延迟预算、恢复窗口、重试次数、受控网络条件和生产 SLO 的最终确认。
- 原始音频与转写的调试授权、数据留存与脱敏规则。
