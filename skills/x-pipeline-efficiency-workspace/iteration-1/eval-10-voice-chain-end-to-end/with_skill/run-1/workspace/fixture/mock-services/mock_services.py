"""本地假 ASR/LLM/TTS：确定性输出，映射真源 fixtures.json。接口见 specs/mock-services.md。"""
import argparse
import hashlib
import json
import pathlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent
FIX = json.loads((ROOT / "fixtures.json").read_text())
ASSETS = ROOT.parent / "assets"

_lock = threading.Lock()
_fault = {}  # service -> {"mode": "500"} | {"hang_ms": int}，单次生效


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n)

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _maybe_fault(self, service):
        """返回 True 表示本次请求已被故障注入应答。"""
        with _lock:
            f = _fault.pop(service, None)
        if not f:
            return False
        if "hang_ms" in f:
            time.sleep(f["hang_ms"] / 1000)
            return False  # 挂够时长后照常应答（调用方应已超时）
        self._json(500, {"error": "injected"})
        return True

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        body = self._body()
        if self.path == "/control":
            req = json.loads(body)
            with _lock:
                if req.get("reset"):
                    _fault.clear()
                else:
                    _fault[req["service"]] = {k: v for k, v in req.items() if k != "service"}
            self._json(200, {"ok": True})
        elif self.path == "/asr":
            if self._maybe_fault("asr"):
                return
            text = FIX["asr"].get(hashlib.sha256(body).hexdigest())
            if text is None:
                self._json(404, {"error": "unknown audio"})
            else:
                self._json(200, {"text": text})
        elif self.path == "/llm":
            if self._maybe_fault("llm"):
                return
            reply = FIX["llm"].get(json.loads(body).get("text", ""))
            if reply is None:
                self._json(400, {"error": "unknown text"})
            else:
                self._json(200, {"reply": reply})
        elif self.path == "/tts":
            if self._maybe_fault("tts"):
                return
            fname = FIX["tts"].get(json.loads(body).get("text", ""))
            if fname is None:
                self._json(400, {"error": "unknown reply"})
                return
            raw = (ASSETS / fname).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            self._json(404, {"error": "not found"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9100)
    args = ap.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
