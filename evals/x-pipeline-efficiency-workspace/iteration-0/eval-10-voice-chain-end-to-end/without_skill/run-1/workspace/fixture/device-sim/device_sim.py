"""仿真设备（相当于一块开发板）：正常路径参考客户端。

- 上传：停等式（每块等 ACK），断线续传按 HELLO ACK 的 last_seq 跳过已传块；
- 下行：把收到的帧载荷原样落盘 out/ 供调试，不做协议解读、不校验细节。

自带独立的帧编解码实现，不依赖 backend/protocol.py（设备固件本就是独立代码）。
"""
import argparse
import hashlib
import json
import pathlib
import socket
import struct
import sys
import zlib

MAGIC = b"\xa5\x5a"
T_HELLO, T_AUDIO_CHUNK, T_AUDIO_END, T_ACK, T_ERROR, T_TTS_CHUNK, T_TTS_END = range(1, 8)
HEADER_LEN, CRC_LEN = 11, 4
CHUNK = 3200  # 真源 specs/audio-format.md


def enc(ftype, seq, payload=b""):
    body = struct.pack(">BII", ftype, seq, len(payload)) + payload
    return MAGIC + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


class Dec:
    def __init__(self):
        self.buf = b""

    def feed(self, data):
        self.buf += data
        out = []
        while len(self.buf) >= HEADER_LEN:
            ftype, seq, plen = struct.unpack(">BII", self.buf[2:HEADER_LEN])
            total = HEADER_LEN + plen + CRC_LEN
            if len(self.buf) < total:
                break
            out.append((ftype, seq, self.buf[HEADER_LEN:HEADER_LEN + plen]))
            self.buf = self.buf[total:]
        return out


def recv_frame(sock, dec, pending):
    while not pending:
        data = sock.recv(65536)
        if not data:
            raise ConnectionError("server closed")
        pending.extend(dec.feed(data))
    return pending.pop(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="host:port")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--session", default="dev-sim-001")
    ap.add_argument("--upload-only", action="store_true")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    raw = pathlib.Path(args.wav).read_bytes()
    chunks = [raw[i:i + CHUNK] for i in range(0, len(raw), CHUNK)]
    host, port = args.server.rsplit(":", 1)

    sock = socket.create_connection((host, int(port)), timeout=15)
    sock.settimeout(15)
    dec, pending = Dec(), []

    sock.sendall(enc(T_HELLO, 0, json.dumps(
        {"device_id": "esp32-sim", "session_id": args.session}).encode()))
    f = recv_frame(sock, dec, pending)
    last = json.loads(f[2])["last_seq"] if f[0] == T_ACK else 0
    print(f"[sim] HELLO ack, last_seq={last}")

    for i, c in enumerate(chunks, 1):
        if i <= last:
            continue
        sock.sendall(enc(T_AUDIO_CHUNK, i, c))
        ack = recv_frame(sock, dec, pending)
        if ack[0] != T_ACK or ack[1] != i:
            print(f"[sim] 块 {i} 未获 ACK：{ack}")
            sys.exit(1)

    sock.sendall(enc(T_AUDIO_END, len(chunks), json.dumps(
        {"total_chunks": len(chunks), "sha256": hashlib.sha256(raw).hexdigest()}).encode()))
    f = recv_frame(sock, dec, pending)
    kind = {T_ACK: "ACK", T_ERROR: "ERROR"}.get(f[0], str(f[0]))
    print(f"[sim] AUDIO_END -> {kind}: {f[2].decode(errors='replace')}")
    if f[0] != T_ACK or args.upload_only:
        sock.close()
        return

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    payload = b""
    n = 0
    while True:
        f = recv_frame(sock, dec, pending)
        if f[0] == T_TTS_CHUNK:
            payload += f[2]
            n += 1
        elif f[0] == T_TTS_END:
            (outdir / "reply_payload.bin").write_bytes(payload)
            print(f"[sim] 下行结束：{n} 块 / {len(payload)} 字节，"
                  f"TTS_END 载荷: {f[2].decode(errors='replace')}")
            print(f"[sim] 载荷已原样落盘 {outdir / 'reply_payload.bin'}（sim 不校验协议细节）")
            break
        else:
            print(f"[sim] 意外帧 type={f[0]}")
            break
    sock.close()


if __name__ == "__main__":
    main()
