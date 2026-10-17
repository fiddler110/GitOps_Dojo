# ctf-checker: runs each target's check.py against a student's live slot
# (POST /check) and gates a candidate app.py before merge (POST /gate).
# Build context is the module root (compose.yml) so targets/ can be COPYed;
# the check scripts live only here, never in a student repo or terminal.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

# Flask/Werkzeug carry the same pins as every target requirements.txt (Werkzeug is
# Flask's WSGI layer and floats unless named): the checker imports the targets' own app
# modules, so drift here would run their code on a different Flask than the lab does.
# Kept on the pip line itself rather than as a comment inside the RUN continuation,
# which not every builder in this stack strips the same way (CTF-D27).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir Flask==3.0.3 Werkzeug==3.1.9

# Seed copy of every target: check.py, proxy.py, seed.py and the pristine app.
COPY targets /targets
COPY ctf-checker/checker.py ctf-checker/gitref.py ctf-controller/flags.py /app/
WORKDIR /app

RUN useradd --uid 10017 --no-create-home --home-dir /app --shell /usr/sbin/nologin ctf-checker
USER ctf-checker

ENV PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    GIT_CONFIG_NOSYSTEM=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 9200
ENTRYPOINT ["python3", "/app/checker.py"]
