"""WAV 解析与设备播放 PCM 分块工具。"""
import struct


# task/specs/audio-format.md 的设备播放格式真源。
PCM_FORMAT = 1
CHANNELS = 1
SAMPLE_RATE = 16000
BITS_PER_SAMPLE = 16
BLOCK_ALIGN = CHANNELS * BITS_PER_SAMPLE // 8
BYTE_RATE = SAMPLE_RATE * BLOCK_ALIGN
PLAYBACK_CHUNK_BYTES = 3200


def wav_pcm(data):
    """校验设备支持的 WAV 格式，并返回 data chunk 的 PCM 裸流。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a wav file")
    riff_size, = struct.unpack("<I", data[4:8])
    if riff_size + 8 > len(data):
        raise ValueError("truncated RIFF")
    off = 12
    fmt = None
    pcm = None
    limit = riff_size + 8
    while off + 8 <= limit:
        cid = data[off:off + 4]
        size, = struct.unpack("<I", data[off + 4:off + 8])
        end = off + 8 + size
        if end > limit or end > len(data):
            raise ValueError("truncated WAV chunk")
        chunk = data[off + 8:end]
        if cid == b"fmt ":
            if size < 16:
                raise ValueError("short fmt chunk")
            fmt = struct.unpack("<HHIIHH", chunk[:16])
        if cid == b"data":
            pcm = chunk
        off = end + (size & 1)
    if fmt is None:
        raise ValueError("no fmt chunk")
    expected = (PCM_FORMAT, CHANNELS, SAMPLE_RATE, BYTE_RATE, BLOCK_ALIGN, BITS_PER_SAMPLE)
    if fmt != expected:
        raise ValueError("unsupported WAV format")
    if pcm is None:
        raise ValueError("no data chunk")
    if len(pcm) % BLOCK_ALIGN:
        raise ValueError("unaligned PCM data")
    return pcm


def chunk_pcm(pcm, size):
    """按 size 切块，最后一块可短。"""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for i in range(0, len(pcm), size):
        yield pcm[i:i + size]
