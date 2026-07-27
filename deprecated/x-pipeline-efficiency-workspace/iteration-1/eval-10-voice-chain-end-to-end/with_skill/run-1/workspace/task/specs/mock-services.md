# 规范：本地假服务（ASR / LLM / TTS）

`fixture/mock-services/mock_services.py` 在一个 HTTP 端口上同时提供三个服务的假实现，
输出完全确定（同输入必同输出），映射真源为 `fixture/mock-services/fixtures.json`。
服务地址以 `backend/config.json` 的 `mock_base_url` 为真源。

启动：`python3 mock_services.py --port 9100`

## 接口

### POST /asr —— 语音转文字

- 请求体：完整 WAV 文件字节，`Content-Type: application/octet-stream`
- 200 应答：`{"text": "<识别文本>"}`
- 404 应答：`{"error": "unknown audio"}`（未收录的音频）

### POST /llm —— 生成回复

- 请求体：`{"text": "<用户文本>"}`，`Content-Type: application/json`
- 200 应答：`{"reply": "<回复文本>"}`
- 400 应答：`{"error": "unknown text"}`

### POST /tts —— 文字转语音

- 请求体：`{"text": "<回复文本>"}`，`Content-Type: application/json`
- 200 应答：WAV 文件字节，`Content-Type: audio/wav`
- 400 应答：`{"error": "unknown reply"}`

### GET /health

- 200 应答：`{"ok": true}`

## POST /control —— 故障注入（测试用）

对**下一次**指定服务的调用注入一次故障，用后自动清除：

- `{"service": "asr", "mode": "500"}`：下一次 /asr 返回 500；
- `{"service": "asr", "hang_ms": 8000}`：下一次 /asr 挂起 8 秒后才正常应答；
- `{"reset": true}`：清空所有未消费的注入。

service 取值 `asr` / `llm` / `tts`。判分器会用它注入故障，你自测也可以用。
