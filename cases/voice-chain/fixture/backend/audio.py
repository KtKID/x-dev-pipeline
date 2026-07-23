"""WAV 解析与 PCM 分块工具。"""
import struct


def wav_pcm(data):
    """从 WAV 文件字节中取出 data 块的 PCM 裸流。"""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a wav file")
    off = 12
    while off + 8 <= len(data):
        cid = data[off:off + 4]
        size, = struct.unpack("<I", data[off + 4:off + 8])
        if cid == b"data":
            return data[off + 8:off + 8 + size]
        off += 8 + size + (size & 1)
    raise ValueError("no data chunk")


def chunk_pcm(pcm, size):
    """按 size 切块，最后一块可短。"""
    for i in range(0, len(pcm), size):
        yield pcm[i:i + size]
