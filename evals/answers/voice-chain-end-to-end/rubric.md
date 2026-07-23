# Voice Chain 端到端隐藏评分

> 仅 grader 可见。Executor 只接收题面、fixture 与被测 pipeline 快照。

## 评分与门禁

共 20 条断言，每条 5 分，总分 100。质量门禁为总分至少 90，同时运行时与 pipeline 证据断言 1—19 全部通过。

评分优先使用 `evaluate.py` 的独立协议客户端、本地回环服务与静态文档检查。关键词命中只作为定位线索，实际行为与可复跑证据决定结果。

## 协议与上传：30 分

1. 流式解码同时处理半包、粘包和连续多帧。
2. BAD_MAGIC、BAD_CRC、PAYLOAD_TOO_LARGE 产生对应 ERROR 并关闭当前连接。
3. HELLO、流水线 AUDIO_CHUNK、AUDIO_END 与 ACK 顺序正确，所有块完成处理。
4. upload.wav 与输入 WAV 逐字节一致，AUDIO_END ACK 含 ok、text、reply。
5. 同一 session_id 重连获得准确 last_seq，并从断点完成全链路。
6. SHA-256 不匹配产生 INTEGRITY_FAIL，跳过上游成功链路。

## 服务编排与故障：25 分

7. ASR → LLM → TTS 成功链路产出正确 text/reply，reply.wav 与 TTS WAV 一致。
8. 任一上游超时在配置时间附近产生 UPSTREAM_TIMEOUT，当前连接有界结束。
9. 5xx 按 retry_max_5xx 追加重试，单次 500 注入后能够成功。
10. 4xx 执行零重试并产生 UPSTREAM_ERROR。
11. 动态 mock_base_url、service_timeout_ms、retry_max_5xx 生效，执行不依赖固定 9100 端口。

## 下行与并发：25 分

12. AUDIO_END ACK 完整发送后才出现 TTS_CHUNK，chunk seq 连续，TTS_END seq 等于总块数。
13. 下行载荷精确等于 TTS WAV 的 PCM data，结束帧提供可验证的完整性摘要。
14. 两个不同 session 并发完成时，ACK、upload.wav、reply.wav 与下行 PCM 全部隔离。
15. 一条连接在下行阶段断开后，服务进程继续服务另一会话。
16. backend 运行时代码只依赖 Python 标准库与工作区本地模块。

## Pipeline 产物与证据：20 分

17. spec3 文档覆盖目标、模块边界、不变量、判断依据、测试层与稳定 Scenario ID，且可交接状态明确。
18. req3 checklist 可由 xdev 解析，完整回指 spec Scenario，依赖图与风险路由有效。
19. dev-report 的 verify 证据覆盖当前 task 的 unit、smoke、e2e 场景，命令可复跑。
20. Executor 自测与隐藏评分均可完成，后台进程被清理，产物留在声明范围内。

## 计量

- `quality_score = passed_assertions * 5`
- `quality_pass_rate = passed_assertions / 20`
- `token_delta = (candidate_total_tokens - baseline_total_tokens) / baseline_total_tokens`
- 晋级条件：`quality_score >= 90`、断言 1—19 全过、`token_delta <= -0.05`
