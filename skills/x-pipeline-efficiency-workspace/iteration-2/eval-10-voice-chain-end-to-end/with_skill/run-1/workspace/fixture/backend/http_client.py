"""HTTP 小客户端：后端调用本地 mock 服务用。超时单位毫秒（真源 config.json）。"""
import http.client
import urllib.error
import urllib.request
import socket

# 本地服务，绕开系统代理（ALL_PROXY 等环境变量会把 127.0.0.1 请求送进代理）
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(url, data, content_type, timeout_ms):
    """返回 (status, body)。调用超时抛 TimeoutError；HTTP 错误码不抛异常，随返回值给出。"""
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": content_type}, method="POST"
    )
    try:
        with _opener.open(req, timeout=timeout_ms / 1000) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (TimeoutError, socket.timeout) as e:
        raise TimeoutError(str(e)) from e
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout)):
            raise TimeoutError(str(e)) from e
        raise
    except http.client.HTTPException as e:
        raise OSError(f"incomplete HTTP response: {e}") from e
