"""WAV 解析与 PCM 分块工具。"""
import struct

PCM_FORMAT = 1
PCM_CHANNELS = 1
PCM_SAMPLE_RATE = 16000
PCM_SAMPLE_WIDTH_BITS = 16
PCM_CHUNK_SIZE = 3200


def wav_pcm(data):
    """校验设备支持的 WAV 参数并返回完整 PCM data 块。"""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a wav file")
    riff_size, = struct.unpack("<I", data[4:8])
    container_end = riff_size + 8
    if container_end != len(data):
        raise ValueError("RIFF size mismatch")

    off = 12
    fmt = None
    pcm = None
    while off + 8 <= container_end:
        cid = data[off:off + 4]
        size, = struct.unpack("<I", data[off + 4:off + 8])
        start = off + 8
        end = start + size
        padded_end = end + (size & 1)
        if end > container_end or padded_end > container_end:
            raise ValueError("truncated wav chunk")
        if cid == b"fmt ":
            if size < 16:
                raise ValueError("invalid fmt chunk")
            fmt = struct.unpack("<HHIIHH", data[start:start + 16])
        if cid == b"data":
            pcm = data[start:end]
        off = padded_end

    if off != container_end:
        raise ValueError("trailing partial wav chunk")

    if fmt is None or pcm is None:
        raise ValueError("missing fmt or data chunk")
    encoding, channels, sample_rate, byte_rate, block_align, bits = fmt
    expected_align = PCM_CHANNELS * PCM_SAMPLE_WIDTH_BITS // 8
    expected_rate = PCM_SAMPLE_RATE * expected_align
    if (
        encoding != PCM_FORMAT
        or channels != PCM_CHANNELS
        or sample_rate != PCM_SAMPLE_RATE
        or bits != PCM_SAMPLE_WIDTH_BITS
        or block_align != expected_align
        or byte_rate != expected_rate
        or len(pcm) % block_align
    ):
        raise ValueError("unsupported wav format")
    if not pcm:
        raise ValueError("empty pcm data")
    return pcm


def chunk_pcm(pcm, size):
    """按 size 切块，最后一块可短。"""
    for i in range(0, len(pcm), size):
        yield pcm[i:i + size]
