"""One exact local origin, and nothing else.

The browser reaches the fixture app only through this process. CONNECT, upgrades,
foreign origins, and malformed framing stop here. This is a language boundary
around one owned app port. It is not an operating system sandbox.
"""
import os
import socket
import sys
import threading
import time
from urllib.parse import quote, urlsplit


LOG_LOCK = threading.Lock()
SLOTS = threading.BoundedSemaphore(4)
MAX_HEADERS = 65536
MAX_BODY = 1024 * 1024
MAX_RESPONSE = 8 * 1024 * 1024
DEADLINE = 8
HOP = {'connection', 'proxy-connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'proxy-authorization', 'te', 'trailer'}


def reject(status, reason):
    return ('reject', status, reason)


def public_target(target):
    """Log a path. Keep only an explicit stylesheet version query."""
    try:
        parts = urlsplit(target or '')
    except ValueError:
        return '/'
    path = parts.path or '/'
    if not path.startswith('/') or path.startswith('//'):
        return '/'
    query = parts.query or ''
    if path.endswith('/app.css') and query.startswith('v=') and len(query) <= 40 and all(ch.isalnum() or ch in '=._-' for ch in query):
        return path + '?' + query
    return path


def log_token(value):
    return quote(value or '', safe='')[:240]


def transaction_open(started, now, limit=DEADLINE):
    return now - started <= limit


def _header_lines(lines):
    if not isinstance(lines, (list, tuple)):
        return reject(400, 'header')
    found, hosts, lengths = {}, [], []
    for line in lines:
        if not isinstance(line, str) or ':' not in line:
            return reject(400, 'header')
        key, value = line.split(':', 1)
        if not key or key != key.strip() or any(ch in key for ch in ' \t'):
            return reject(400, 'header')
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in key + value):
            return reject(400, 'header')
        name = key.lower()
        value = value.strip()
        if name in {'host', 'content-length', 'transfer-encoding', 'upgrade'} and name in found:
            return reject(400, 'duplicate')
        found[name] = value
        if name == 'host':
            hosts.append(value)
        elif name == 'content-length':
            lengths.append(value)
    return ('ok', found, hosts, lengths)


def decide(parts, header_lines, app_port):
    """Return forward or reject. No socket is opened here."""
    if not isinstance(parts, (list, tuple)) or len(parts) != 3:
        return reject(400, 'request')
    method, target, version = parts
    method = (method or '').upper()
    if version not in {'HTTP/1.0', 'HTTP/1.1'}:
        return reject(400, 'request')
    if method == 'CONNECT':
        return reject(403, 'connect')
    if method not in {'GET', 'HEAD', 'POST', 'DELETE'}:
        return reject(403, 'method')
    parsed = _header_lines(header_lines)
    if parsed[0] != 'ok':
        return parsed
    headers, hosts, lengths = parsed[1], parsed[2], parsed[3]
    if headers.get('upgrade', '').strip():
        return reject(403, 'upgrade')
    if headers.get('transfer-encoding', '').strip():
        return reject(400, 'transfer-encoding')
    if len(hosts) != 1 or hosts[0] != f'127.0.0.1:{app_port}':
        return reject(400 if len(hosts) != 1 else 403, 'host')
    if len(lengths) > 1:
        return reject(400, 'content-length')
    if lengths:
        length = lengths[0]
        if not length.isdigit():
            return reject(400, 'content-length')
        if int(length) > MAX_BODY:
            return reject(413, 'content-length')
    try:
        url = urlsplit(target or '')
        port = url.port
    except ValueError:
        return reject(400, 'url')
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or port != app_port
            or url.username or url.password or url.fragment):
        return reject(403, 'origin')
    path = url.path or '/'
    if url.query:
        path = path + '?' + url.query
    if not path.startswith('/') or path.startswith('//'):
        return reject(403, 'origin')
    return ('forward', path, '')


def _response(status, reason):
    body = f'proxy rejected {reason}\n'.encode()
    head = (
        f'HTTP/1.1 {status} {reason}\r\nContent-Type: text/plain\r\n'
        f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n'
    ).encode()
    return head + body


def _response_headers(blob):
    lines = blob.decode('iso-8859-1', 'replace').split('\r\n')
    found = {}
    for line in lines[1:]:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        found[key.strip().lower()] = value.strip()
    return found


def _recv_limited(conn, count, started):
    remaining = DEADLINE - (time.monotonic() - started)
    if remaining <= 0:
        return None
    conn.settimeout(remaining)
    try:
        return conn.recv(count)
    except socket.timeout:
        return None


def _read_headers(conn, started):
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = _recv_limited(conn, 4096, started)
        if not chunk:
            return None
        data += chunk
        if len(data) > MAX_HEADERS:
            return None
    head, extra = data.split(b'\r\n\r\n', 1)
    return head, extra


def read_counted_body(conn, already, needed, started):
    """Read an exact Content-Length. None means the body ended early or the deadline closed."""
    data = already
    while len(data) < needed:
        chunk = _recv_limited(conn, min(65536, needed - len(data)), started)
        if not chunk:
            return None
        data += chunk
    return data


def _log(log_path, line):
    with LOG_LOCK:
        with open(log_path, 'a', encoding='utf-8') as handle:
            handle.write(line.rstrip() + '\n')


def handle(conn, app_port, log_path):
    started = time.monotonic()
    conn.settimeout(2)
    try:
        parsed = _read_headers(conn, started)
        if parsed is None or not transaction_open(started, time.monotonic()):
            conn.sendall(_response(400, 'headers'))
            return
        head, extra = parsed
        lines = head.decode('iso-8859-1', 'replace').split('\r\n')
        parts = lines[0].split(' ')
        outcome = decide(parts, lines[1:], app_port)
        method = parts[0] if parts else ''
        if outcome[0] != 'forward':
            _log(log_path, f'REJECT {outcome[1]} {outcome[2]} {method} {public_target(parts[1] if len(parts) > 1 else "/")}')
            conn.sendall(_response(outcome[1], outcome[2]))
            return
        headers = _header_lines(lines[1:])[1]
        length = int(headers['content-length']) if 'content-length' in headers else 0
        body = b''
        if length:
            body = read_counted_body(conn, extra, length, started)
            if body is None:
                conn.sendall(_response(400, 'body'))
                return
        path = outcome[1]
        forwarded = [f'{method} {path} HTTP/1.0', f'Host: 127.0.0.1:{app_port}', 'Connection: close']
        for key, value in headers.items():
            if key in HOP or key in {'host', 'content-length'}:
                continue
            forwarded.append(f'{key}: {value}')
        if length:
            forwarded.append(f'Content-Length: {length}')
        upstream = socket.create_connection(('127.0.0.1', app_port), timeout=10)
        try:
            upstream.sendall(('\r\n'.join(forwarded) + '\r\n\r\n').encode('iso-8859-1') + body)
            response = b''
            while b'\r\n\r\n' not in response and len(response) <= MAX_HEADERS:
                chunk = _recv_limited(upstream, 65536, started)
                if not chunk:
                    break
                response += chunk
            if b'\r\n\r\n' not in response:
                conn.sendall(_response(502, 'upstream'))
                _log(log_path, f'REJECT 502 upstream {method} {public_target(path)}')
                return
            raw_head, raw_body = response.split(b'\r\n\r\n', 1)
            response_headers = _response_headers(raw_head)
            expected = response_headers.get('content-length', '')
            if expected.isdigit():
                needed = int(expected)
                if needed > MAX_RESPONSE:
                    conn.sendall(_response(502, 'upstream-length'))
                    _log(log_path, f'REJECT 502 upstream-length {method} {public_target(path)}')
                    return
                completed = read_counted_body(upstream, raw_body, needed, started)
                if completed is None:
                    conn.sendall(_response(502, 'upstream-length'))
                    _log(log_path, f'REJECT 502 upstream-length {method} {public_target(path)}')
                    return
                raw_body = completed
            else:
                while len(raw_body) <= MAX_RESPONSE:
                    chunk = _recv_limited(upstream, 65536, started)
                    if chunk is None:
                        conn.sendall(_response(502, 'upstream-length'))
                        _log(log_path, f'REJECT 502 upstream-length {method} {public_target(path)}')
                        return
                    if not chunk:
                        break
                    raw_body += chunk
            if len(raw_body) > MAX_RESPONSE:
                conn.sendall(_response(502, 'upstream-length'))
                _log(log_path, f'REJECT 502 upstream-length {method} {public_target(path)}')
                return
            status_line = raw_head.split(b'\r\n', 1)[0].decode('iso-8859-1', 'replace')
            status = status_line.split(' ')[1] if ' ' in status_line else '0'
            filtered = [status_line, 'Connection: close', f'Content-Length: {len(raw_body)}']
            for key, value in response_headers.items():
                if key in HOP or key == 'content-length':
                    continue
                filtered.append(f'{key}: {value}')
            conn.sendall(('\r\n'.join(filtered) + '\r\n\r\n').encode('iso-8859-1') + raw_body)
            _log(log_path, ' '.join([
                'FORWARD', method, public_target(path), status,
                'req_inm=' + log_token(headers.get('if-none-match', '')),
                'req_ims=' + log_token(headers.get('if-modified-since', '')),
                'etag=' + log_token(response_headers.get('etag', '')),
                'cache=' + log_token(response_headers.get('cache-control', '')),
            ]))
        finally:
            upstream.close()
    except OSError as exc:
        _log(log_path, f'REJECT 502 socket {exc.__class__.__name__}')
        try:
            conn.sendall(_response(502, 'socket'))
        except OSError:
            pass
    finally:
        conn.close()


def serve(listen_fd, app_port, log_path):
    """Accept only as many connections as the bounded worker slots."""
    sock = socket.socket(fileno=listen_fd)
    sock.settimeout(1)

    def run(conn):
        try:
            handle(conn, app_port, log_path)
        finally:
            SLOTS.release()

    while True:
        try:
            conn, _addr = sock.accept()
        except socket.timeout:
            continue
        if not SLOTS.acquire(blocking=False):
            try:
                conn.sendall(_response(503, 'busy'))
            except OSError:
                pass
            conn.close()
            continue
        threading.Thread(target=run, args=(conn,), daemon=True).start()


def main():
    serve(int(os.environ['PROXY_LISTEN_FD']), int(os.environ['APP_PORT']), os.environ['PROXY_LOG'])


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
