"""FileResponse headers with bounded asynchronous reads under ASGI."""
from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.http import FileResponse


def private_file_response(request, handle, **kwargs):
    response = FileResponse(handle, **kwargs)
    if isinstance(request, ASGIRequest):
        async def chunks():
            try:
                while True:
                    chunk = await sync_to_async(handle.read, thread_sensitive=False)(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                await sync_to_async(handle.close, thread_sensitive=False)()
        response.streaming_content = chunks()
    return response
