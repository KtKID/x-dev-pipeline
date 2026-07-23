"""具有整次调用 deadline 的最小 HTTP/1.1 POST 客户端。"""
import socket
import time
import urllib.parse


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("HTTP call exceeded total deadline")
    return remaining


def _send_all(sock, data, deadline):
    view = memoryview(data)
    while view:
        sock.settimeout(_remaining(deadline))
        sent = sock.send(view)
        if sent <= 0:
            raise OSError("HTTP connection closed while sending")
        view = view[sent:]


def _recv(sock, deadline):
    sock.settimeout(_remaining(deadline))
    data = sock.recv(8192)
    if not data:
        raise OSError("HTTP connection closed before response completed")
    return data


def post(url, data, content_type, timeout_ms):
    """返回 ``(status, body)``；整个调用超过配置毫秒数时抛 TimeoutError。"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise OSError("only absolute http URLs are supported")
    port = parsed.port or 80
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    host_header = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{port}"
    request = (
        f"POST {target} HTTP/1.1\r\n"
        f"Host: {host_header}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(data)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + data

    deadline = time.monotonic() + timeout_ms / 1000
    sock = None
    try:
        sock = socket.create_connection(
            (parsed.hostname, port), timeout=_remaining(deadline)
        )
        _send_all(sock, request, deadline)
        response = b""
        while b"\r\n\r\n" not in response:
            response += _recv(sock, deadline)
        header_bytes, body = response.split(b"\r\n\r\n", 1)
        lines = header_bytes.split(b"\r\n")
        try:
            status = int(lines[0].split(b" ", 2)[1])
            headers = {}
            for line in lines[1:]:
                name, value = line.split(b":", 1)
                headers[name.strip().lower()] = value.strip()
            content_length = int(headers[b"content-length"])
        except (IndexError, KeyError, ValueError) as exc:
            raise OSError("invalid HTTP response") from exc
        if content_length < 0:
            raise OSError("negative HTTP Content-Length")
        while len(body) < content_length:
            body += _recv(sock, deadline)
        return status, body[:content_length]
    except socket.timeout as exc:
        raise TimeoutError("HTTP call exceeded total deadline") from exc
    finally:
        if sock is not None:
            sock.close()
