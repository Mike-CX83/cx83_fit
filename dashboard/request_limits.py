"""Bound incoming Django bodies before its ASGI handler spools them to disk.

MCP retains the SDK's separate 64 KiB body limit. This wrapper is deliberately
around Django only: on rejection, a disconnect event lets Django close its body
file and abort before dispatch. We then return the private transport error.
"""
import asyncio


FORM_LIMIT = 64 * 1024
MULTIPART_ALLOWANCE = 16 * 1024
UPLOAD_LIMITS = {
    '/measurements/import/': 64 * 1024 + MULTIPART_ALLOWANCE,
    '/summaries/import/': 256 * 1024 + MULTIPART_ALLOWANCE,
    '/photos/new/': 12 * 1024 * 1024 + MULTIPART_ALLOWANCE,
}


class DjangoRequestLimits:
    def __init__(self, app, *, idle_seconds=15, total_seconds=120):
        self.app = app
        self.idle_seconds = idle_seconds
        self.total_seconds = total_seconds

    @staticmethod
    async def reject(send, status):
        body = {
            400: b'Invalid request length.',
            408: b'Upload timed out. Please retry.',
            413: b'Request exceeds the upload limit.',
        }[status]
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', b'text/plain; charset=utf-8'),
            (b'content-length', str(len(body)).encode()),
            (b'cache-control', b'private, no-store'),
            (b'x-content-type-options', b'nosniff'),
            (b'referrer-policy', b'same-origin'),
            (b'content-security-policy', b"default-src 'none'; frame-ancestors 'none'"),
        ]})
        await send({'type': 'http.response.body', 'body': body})

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        limit = UPLOAD_LIMITS.get(scope.get('path'), FORM_LIMIT)
        lengths = [value for name, value in scope.get('headers', []) if name.lower() == b'content-length']
        if lengths:
            if len(lengths) != 1 or not lengths[0].isdigit() or len(lengths[0]) > 20:
                return await self.reject(send, 400)
            if int(lengths[0]) > limit:
                return await self.reject(send, 413)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.total_seconds
        received = 0
        finished = False
        rejected = None

        async def bounded_receive():
            nonlocal received, finished, rejected
            # Once the body ends, Django listens for client disconnection during
            # view execution/downloads. Upload timeouts must not cancel those.
            if finished:
                return await receive()
            remaining = min(self.idle_seconds, deadline - loop.time())
            try:
                if remaining <= 0:
                    raise TimeoutError
                message = await asyncio.wait_for(receive(), timeout=remaining)
            except TimeoutError:
                rejected = 408
                return {'type': 'http.disconnect'}
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > limit:
                    rejected = 413
                    return {'type': 'http.disconnect'}
                finished = not message.get('more_body', False)
            return message

        await self.app(scope, bounded_receive, send)
        if rejected:
            await self.reject(send, rejected)
