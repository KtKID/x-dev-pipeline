"""HTTP 小客户端：后端调用本地 mock 服务用。超时单位毫秒（真源 config.json）。"""
import http.client
import io
import socket
import threading
import time
import urllib.parse


def post(url, data, content_type, timeout_ms):
    """返回 (status, body)。调用超时抛 TimeoutError；HTTP 错误码不抛异常，随返回值给出。"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise OSError("invalid upstream URL")
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    deadline = time.monotonic() + timeout_ms / 1000

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError(f"timeout calling {url}")
        return value

    path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection = None
    response = None
    expired = threading.Event()
    finished = threading.Event()

    def response_socket():
        if response is None:
            return None
        buffered = getattr(response, "fp", None)
        return getattr(getattr(buffered, "raw", None), "_sock", None)

    def abort_at_deadline():
        if finished.is_set():
            return
        expired.set()
        active_socket = connection.sock if connection is not None else None
        active_socket = active_socket or response_socket()
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                active_socket.close()
            except OSError:
                pass

    deadline_timer = threading.Timer(timeout_ms / 1000, abort_at_deadline)
    deadline_timer.daemon = True

    def set_socket_timeout():
        active_socket = connection.sock
        if active_socket is None:
            active_socket = response_socket()
        if active_socket is not None:
            active_socket.settimeout(remaining())

    try:
        connection = connection_type(parsed.hostname, parsed.port, timeout=remaining())
        deadline_timer.start()
        connection.request(
            "POST",
            path,
            body=data,
            headers={"Content-Type": content_type, "Content-Length": str(len(data))},
        )
        set_socket_timeout()
        response = connection.getresponse()
        chunks = []
        while True:
            set_socket_timeout()
            chunk = response.read1(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            chunks.append(chunk)
        if response.length not in (None, 0):
            raise http.client.IncompleteRead(b"".join(chunks), response.length)
        if expired.is_set():
            raise TimeoutError(f"timeout calling {url}")
        finished.set()
        deadline_timer.cancel()
        return response.status, b"".join(chunks)
    except (TimeoutError, socket.timeout) as e:
        raise TimeoutError(str(e)) from e
    except (http.client.HTTPException, ValueError, OSError) as e:
        if expired.is_set():
            raise TimeoutError(f"timeout calling {url}") from e
        raise OSError(f"invalid upstream HTTP response: {e}") from e
    finally:
        finished.set()
        deadline_timer.cancel()
        if response is not None:
            response.close()
        if connection is not None:
            connection.close()
