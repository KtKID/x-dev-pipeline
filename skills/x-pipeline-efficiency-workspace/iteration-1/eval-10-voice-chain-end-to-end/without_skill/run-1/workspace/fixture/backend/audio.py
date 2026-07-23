"""Strict WAV parsing and PCM chunking for the device playback contract."""
import struct


PCM_FORMAT = 1


def wav_pcm(data, sample_rate=16000, channels=1, bits_per_sample=16):
    """Validate a RIFF/WAVE PCM file and return its complete data chunk."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a WAV file")
    riff_size, = struct.unpack("<I", data[4:8])
    end = riff_size + 8
    if end != len(data):
        raise ValueError("invalid RIFF size")

    offset = 12
    fmt = None
    pcm = None
    while offset < end:
        if offset + 8 > end:
            raise ValueError("truncated WAV chunk header")
        chunk_id = data[offset:offset + 4]
        size, = struct.unpack("<I", data[offset + 4:offset + 8])
        start = offset + 8
        chunk_end = start + size
        padded_end = chunk_end + (size & 1)
        if chunk_end > end or padded_end > end:
            raise ValueError("truncated WAV chunk")
        chunk = data[start:chunk_end]
        if chunk_id == b"fmt " and fmt is None:
            if size < 16:
                raise ValueError("invalid fmt chunk")
            fmt = struct.unpack("<HHIIHH", chunk[:16])
        elif chunk_id == b"data" and pcm is None:
            pcm = chunk
        offset = padded_end

    if fmt is None or pcm is None or not pcm:
        raise ValueError("missing WAV fmt or data chunk")
    audio_format, actual_channels, actual_rate, _, block_align, actual_bits = fmt
    bytes_per_sample = bits_per_sample // 8
    if (
        audio_format != PCM_FORMAT
        or actual_channels != channels
        or actual_rate != sample_rate
        or actual_bits != bits_per_sample
        or bits_per_sample % 8
        or block_align != channels * bytes_per_sample
        or len(pcm) % block_align
    ):
        raise ValueError("unsupported WAV playback format")
    return pcm


def chunk_pcm(pcm, size):
    """Yield non-empty PCM blocks no larger than the configured size."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for offset in range(0, len(pcm), size):
        yield pcm[offset:offset + size]
