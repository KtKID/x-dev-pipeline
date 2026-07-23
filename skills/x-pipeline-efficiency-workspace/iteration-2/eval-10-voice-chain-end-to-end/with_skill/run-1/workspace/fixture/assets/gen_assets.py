"""生成确定性音频素材（正弦音 WAV，16k/16bit/单声道）并写出 mock-services/fixtures.json。

时长刻意选成"PCM 长度不是 3200 整数倍"，让最后一块是短块（边界条件靠素材保证）。
"""
import hashlib
import json
import math
import pathlib
import struct
import wave

ROOT = pathlib.Path(__file__).resolve().parent
SR = 16000

# (文件名, 频率Hz, 时长秒, ASR 识别文本)
UPLOADS = [
    ("ask_weather.wav", 440, 1.003, "今天天气怎么样"),
    ("ask_time.wav", 550, 1.271, "现在几点了"),
]
# (用户文本, LLM 回复, TTS 文件名, 频率Hz, 时长秒)
REPLIES = [
    ("今天天气怎么样", "今天晴，气温二十六度", "tts_weather.wav", 660, 0.833),
    ("现在几点了", "现在是下午三点", "tts_time.wav", 770, 0.611),
]


def synth(path, freq, seconds):
    n = int(SR * seconds)
    frames = b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / SR)))
        for i in range(n)
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(frames)
    return path.read_bytes()


def main():
    fix = {"asr": {}, "llm": {}, "tts": {}}
    for fname, freq, sec, text in UPLOADS:
        raw = synth(ROOT / fname, freq, sec)
        fix["asr"][hashlib.sha256(raw).hexdigest()] = text
    for text, reply, fname, freq, sec in REPLIES:
        raw = synth(ROOT / fname, freq, sec)
        fix["llm"][text] = reply
        fix["tts"][reply] = fname
        pcm_len = len(raw) - 44
        assert pcm_len % 3200 != 0, f"{fname} PCM 长度是块整数倍，起不到短块边界作用"
    out = ROOT.parent / "mock-services" / "fixtures.json"
    out.write_text(json.dumps(fix, ensure_ascii=False, indent=2))
    print(f"生成完成：{len(UPLOADS) + len(REPLIES)} 个 wav + {out}")


if __name__ == "__main__":
    main()
