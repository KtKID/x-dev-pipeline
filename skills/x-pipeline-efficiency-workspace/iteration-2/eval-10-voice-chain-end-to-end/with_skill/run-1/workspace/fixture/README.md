# 起始环境说明

| 目录 | 是什么 | 你要动吗 |
|---|---|---|
| `backend/` | 后端骨架，你的主战场 | 要，需求见题面 |
| `device-sim/` | 仿真设备（相当于一块开发板），正常路径参考客户端 | 不用改 |
| `mock-services/` | 本地假 ASR/LLM/TTS，确定性输出 | 不用改 |
| `assets/` | 预录音频素材（由 `assets/gen_assets.py` 生成，已生成好） | 不用改 |

## 快速起环境

```bash
# 终端 1：假服务
python3 mock-services/mock_services.py --port 9100

# 终端 2：后端（你实现的）
cd backend && python3 app.py --port 9000 --config config.json

# 终端 3：仿真设备上传一句话
python3 device-sim/device_sim.py --server 127.0.0.1:9000 --wav assets/ask_weather.wav
```

## 素材对照表（自测用）

| 上传音频 | ASR 识别 | LLM 回复 | TTS 素材 |
|---|---|---|---|
| `ask_weather.wav` | 今天天气怎么样 | 今天晴，气温二十六度 | `tts_weather.wav` |
| `ask_time.wav` | 现在几点了 | 现在是下午三点 | `tts_time.wav` |
