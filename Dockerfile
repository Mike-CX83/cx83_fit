# Pinned upstream multi-platform digest; release verification targets linux/amd64.
FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && groupadd --gid 10001 healthapp \
    && useradd --uid 10001 --gid 10001 --no-create-home healthapp \
    && install -d -m 0700 /data \
    && mkdir -p /app/staticfiles \
    && chown -R healthapp:healthapp /data /app
COPY --chown=healthapp:healthapp dashboard ./dashboard
COPY --chown=healthapp:healthapp tracking ./tracking
COPY --chown=healthapp:healthapp manage.py ./manage.py
COPY --chmod=0555 deploy/container-entrypoint.sh /app/container-entrypoint.sh
USER 10001:10001
# Collect public CSS only. This throwaway build key is never used by runtime.
RUN DJANGO_SECRET_KEY=build-only-placeholder-not-used-at-runtime-000000000000000000000 \
    OWNER_USERNAME=build-only DASHBOARD_LOCAL_ONLY=1 \
    DASHBOARD_PRIVATE_ROOT=/tmp/build-private python manage.py collectstatic --noinput
ENV DASHBOARD_PRIVATE_ROOT=/data
EXPOSE 8000
ENTRYPOINT ["/app/container-entrypoint.sh"]
CMD ["uvicorn", "dashboard.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
