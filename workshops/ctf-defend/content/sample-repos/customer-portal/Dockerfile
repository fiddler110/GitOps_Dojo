FROM topiary/ctf-customer-portal-base:pinned

COPY app.py seed.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

RUN useradd --uid 10014 --no-create-home --home-dir /app --shell /usr/sbin/nologin portal \
    && mkdir -p /data \
    && chown portal:portal /data
VOLUME /data

ENV CTF_DB_PATH=/data/portal.db \
    PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000

USER portal
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
