"""WAV 解析与 PCM 分块工具。"""
import io
import wave


# task/specs/audio-format.md 的音频数值真源在代码中的命名投影。
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2
PCM_SAMPLE_RATE = 16000
AUDIO_BLOCK_SIZE = 3200


def wav_pcm(data):
    """校验设备支持的 WAV 参数并返回 PCM 裸流。"""
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            if source.getcomptype() != "NONE":
                raise ValueError("WAV must contain uncompressed PCM")
            if source.getnchannels() != PCM_CHANNELS:
                raise ValueError("WAV must be mono")
            if source.getsampwidth() != PCM_SAMPLE_WIDTH:
                raise ValueError("WAV must use 16-bit samples")
            if source.getframerate() != PCM_SAMPLE_RATE:
                raise ValueError("WAV must use 16000 Hz")
            pcm = source.readframes(source.getnframes())
    except (EOFError, wave.Error) as exc:
        raise ValueError("invalid WAV") from exc
    if not pcm:
        raise ValueError("WAV contains no PCM frames")
    return pcm


def chunk_pcm(pcm, size):
    """按 size 切块，最后一块可短。"""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for i in range(0, len(pcm), size):
        yield pcm[i:i + size]
