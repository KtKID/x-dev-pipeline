"""帧编解码：格式真源见 specs/wire-protocol.md。"""
import struct
import zlib

MAGIC = b"\xa5\x5a"
T_HELLO = 0x01
T_AUDIO_CHUNK = 0x02
T_AUDIO_END = 0x03
T_ACK = 0x04
T_ERROR = 0x05
T_TTS_CHUNK = 0x06
T_TTS_END = 0x07

HEADER_LEN = 2 + 1 + 4 + 4
CRC_LEN = 4
MAX_PAYLOAD = 262144


class ProtocolError(Exception):
    """携带 wire-protocol.md 定义的错误码。"""

    def __init__(self, code, seq=0, frames=()):
        super().__init__(code)
        self.code = code
        self.seq = seq
        self.frames = tuple(frames)


def encode_frame(ftype, seq, payload=b""):
    body = struct.pack(">BII", ftype, seq, len(payload)) + payload
    crc = zlib.crc32(body) & 0xFFFFFFFF
    return MAGIC + body + struct.pack(">I", crc)


class FrameDecoder:
    """流式解码器：feed() 喂入任意长度字节，返回已凑齐的完整帧列表（处理粘包/半包）。"""

    def __init__(self):
        self.buf = b""

    def feed(self, data):
        self.buf += data
        frames = []
        while True:
            if len(self.buf) >= len(MAGIC) and self.buf[:2] != MAGIC:
                raise ProtocolError("BAD_MAGIC", frames=frames)
            if len(self.buf) < HEADER_LEN:
                break
            ftype, seq, plen = struct.unpack(">BII", self.buf[2:HEADER_LEN])
            if plen > MAX_PAYLOAD:
                raise ProtocolError("PAYLOAD_TOO_LARGE", seq, frames)
            total = HEADER_LEN + plen + CRC_LEN
            if len(self.buf) < total:
                break
            body = self.buf[2:HEADER_LEN + plen]
            crc, = struct.unpack(">I", self.buf[HEADER_LEN + plen:total])
            if zlib.crc32(body) & 0xFFFFFFFF != crc:
                raise ProtocolError("BAD_CRC", seq, frames)
            frames.append((ftype, seq, self.buf[HEADER_LEN:HEADER_LEN + plen]))
            self.buf = self.buf[total:]
        return frames
