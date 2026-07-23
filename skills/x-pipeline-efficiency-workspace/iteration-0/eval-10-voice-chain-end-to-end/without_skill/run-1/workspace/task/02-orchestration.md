# 考题②：ASR → LLM → TTS 服务编排

> 附件清单（随卷必发）：`specs/audio-format.md`、`specs/wire-protocol.md`、`specs/mock-services.md`
> 前置：本题建立在考题①（上传通道）之上。单发本卷时，快照内已附带一份可用的上传实现。

## 背景

设备音频上传完成后，后端要依次调用三个服务：语音转文字（ASR）→ 大模型（LLM）→
文字转语音（TTS），得到回复语音。三个服务由 `fixture/mock-services/` 的本地假服务提供，
接口见 `specs/mock-services.md`，输出完全确定（同输入必同输出），方便你自测。

## 需求

1. AUDIO_END 完整性校验通过后，依次调用 ASR / LLM / TTS；
2. 结果落盘：TTS 返回的音频原样写入 `sessions/<session_id>/reply.wav`；
3. AUDIO_END 的 ACK 载荷携带 `{"ok": true, "text": <ASR识别文本>, "reply": <LLM回复文本>}`；
4. 失败处理（对每个服务调用生效）：
   - 调用超时：不重试，向设备回 ERROR 帧，code=`UPSTREAM_TIMEOUT`；
   - 返回 5xx：重试，次数上限走配置 `retry_max_5xx`；重试后仍失败回 ERROR，code=`UPSTREAM_ERROR`；
   - 返回 4xx（如未收录的音频）：不重试，回 ERROR，code=`UPSTREAM_ERROR`；
   - 无论哪种失败，设备侧必须在有限时间内收到应答，不允许挂死；
5. 并发隔离：多台设备同时上传对话，各自会话的 text/reply/落盘文件互不串扰。

## 约束

- 只准用 Python 标准库；
- 超时时长、重试次数以 `backend/config.json` 为真源（注意单位，配置里是毫秒）；
- 骨架提供的 `http_client.py` 可用可改，**对其正确性负责的是你**；
- 后端启动契约（判分依赖，勿改）：`python3 app.py --port 9000 --config config.json`。

## 交付与自测

- 自测：先起假服务 `python3 ../mock-services/mock_services.py --port 9100`，再起后端，
  用仿真设备上传 `assets/ask_weather.wav`，观察 ACK 载荷与 `sessions/` 落盘；
- 假服务提供 `/control` 故障注入接口（见 `specs/mock-services.md`），供你自测超时/5xx 路径；
- 按你自己的开发流程产出规划/设计/验证文档，判分会按评分表评审。
- 规范未尽事宜：向出题人提问澄清，或在文档中显式记录你的假设。
