ARG BASE=gitopsdojo/ctf-customer-portal-base:pinned
FROM ${BASE}

COPY requirements.txt /app/requirements.txt

COPY app.py /app/app.py

RUN useradd --uid 10023 --no-create-home --home-dir /app --shell /usr/sbin/nologin leakyconfig

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000 2222

USER leakyconfig
WORKDIR /app
ENTRYPOINT ["python3", "/app/app.py"]
