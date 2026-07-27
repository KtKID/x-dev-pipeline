# x-fix 阻断报告 — voice-chain/backend

> 状态：Gate① 通过，Gate② R3 未通过
> fix-counter：3 / 3
> 问题账本：`reports/qa-gate/qa-gate-report-20260723-030547.md`

## 已完成事实

- R1 发现并修复 2 个 P1：同批有效帧在后续坏 CRC 时丢失、RIFF 声明边界未校验。
- R2 经过两轮修复关闭 3 个 P1：启动配置/端口校验、截断 HTTP 归一化、覆盖响应头与 body 的总截止时间。
- 完整测试：23 tests 全部通过。
- Gate①：pass 18、manual 0、uncovered 0。
- R1 与 R2 最终增量复审均确认无剩余 P0/P1。

## 阻塞原因

R3 测试真实性审查仍有 9 个 P1。共享修复计数器已达到三轮上限，冻结 `x-fix` 协议禁止进入第 4 轮，因此 checklist 保持 `[!] 🔴`，Gate② 无法签发最终通过。

## 待处理 P1

| issue | 范围 | 证据缺口 |
|---|---|---|
| issue-1 | SC_12/SC_13 | PCM 期望复用生产解析器，同源截断错误可逃逸 |
| issue-2 | SC_06 | 未直接证明 ASR 未调用、续传状态保留及 ERROR 后 EOF |
| issue-3 | SC_08 | 真实超时只覆盖 ASR，LLM/TTS 接线缺少证据 |
| issue-4 | SC_09 | 真实 5xx 重试只覆盖 LLM，ASR/TTS 接线缺少证据 |
| issue-5 | SC_10 | 4xx/耗尽 5xx 缺少 fenced 线级 ERROR、关闭和服务存活证据 |
| issue-6 | SC_11 | 缺少强制并发重叠及 reply/reply.wav/PCM 的独立全量核对 |
| issue-7 | SC_12 | 无效 TTS WAV 未经过真实 TCP handler 验证 ERROR 与连接关闭 |
| issue-8 | SC_13 | simulator 不校验 TTS 块大小、序号与 TTS_END 元数据 |
| issue-9 | SC_14 | 断连时机未保证击中剩余下行，另一会话也未强制重叠 |

## 已登记 P2

- session 状态无界保留；会话锁覆盖上游与下行发送；同连接重复 AUDIO_END 可重复播放。
- 无效 `reply.wav` 在格式校验前发布；`encode_frame` 缺载荷上限；WAV 重复关键 chunk 未拒绝。
- SC_02 缺重复/变化/空洞断点反例；超时断言容差偏宽。

## 需要的决策

1. 授权第 4 轮修复：补齐 9 个 P1 证据后复跑 Gate① 与 R3 增量复审。
2. 调整验收强度：将指定证据缺口降为 P2，再继续 Gate②。
3. 接受当前实现与 Gate① 结果，以 Gate② 未通过状态交付。
