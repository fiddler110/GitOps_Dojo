# ctf-defend-test's own link in the terminal chain. No extra tools (dump.py and this hook are
# stdlib curl/python3, already in the base image) -- just the start.d hook.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY start.d/90-ctf-defend-test.sh /etc/dojo/start.d/90-ctf-defend-test.sh
COPY start.d/95-tfstate-treasure.sh /etc/dojo/start.d/95-tfstate-treasure.sh
COPY start.d/96-runner-escape.sh /etc/dojo/start.d/96-runner-escape.sh
RUN chmod 0755 /etc/dojo/start.d/90-ctf-defend-test.sh /etc/dojo/start.d/95-tfstate-treasure.sh \
      /etc/dojo/start.d/96-runner-escape.sh
