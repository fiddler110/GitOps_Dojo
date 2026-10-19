ARG BASE=gitopsdojo/ctf-customer-portal-base:pinned
FROM ${BASE}

COPY requirements.txt /app/requirements.txt

COPY policy_engine.py /app/policy_engine.py
COPY app.py /app/app.py
COPY proxy.py entrypoint.sh /app/

RUN useradd --uid 10025 --no-create-home --home-dir /app --shell /usr/sbin/nologin policybypass

ENV PORT=5000 \
    PYTHONUNBUFFERED=1
EXPOSE 5000 2222

USER policybypass
WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
