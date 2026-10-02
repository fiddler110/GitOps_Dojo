# sensei module's link in the terminal build chain: the `sensei` command (see sensei.py).
# No ENTRYPOINT here; the chain's entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY sensei.py /usr/local/bin/sensei
RUN chmod 0755 /usr/local/bin/sensei
