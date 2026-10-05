# ctf-range module's link in the terminal build chain (engine/run.sh sets
# BASE to the image below this one; see workshops/README.md). Adds
# `dojo-flag` (plan §5), the per-uid ctf_net firewall hook (CTF-S2/S3), the
# offensive tool suite and the Lab Info library that documents it (plan §9,
# CTF-D16, CTF-P2b) - one shared set installed once here because CTF-D16
# ships the same tools and the same primers to every session pack
# regardless of which targets it uses.
#
# Deliberately NOT here: metasploit, which the plan explicitly keeps out of
# the terminal image as too large.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY dojo-flag.py /usr/local/bin/dojo-flag
COPY start.d/50-ctf-range.sh /etc/dojo/start.d/50-ctf-range.sh
RUN chmod 0755 /usr/local/bin/dojo-flag /etc/dojo/start.d/50-ctf-range.sh

# dojo-flag talks to ctf-flags directly on workshop_lab, not through the
# gateway (same shape as openbao's BAO_ADDR - see modules/openbao/terminal).
ENV CTF_FLAGS_ADDR=http://ctf-flags:8080

# Debian-packaged tools (plan §9): apt itself verifies these against
# Debian's signed repo metadata, the same trust basis every other apt
# install in this repo already relies on (see engine/web-terminal's base
# package list) - no extra per-binary sha256 for these.
#   nmap        host/port discovery, service versions (target 0 etc.)
#   ncat        raw TCP/UDP for reading what a scan found
#   tcpdump     packet capture from the shell
#   tshark      packet capture with protocol decode (console Wireshark)
#   sqlmap      SQLi discovery/exploitation (target 14's own class, 1 etc.)
#   jq          JSON on the command line (targets 12/13's APIs)
#   john        offline hash cracking (chosen over hashcat: CPU-only here,
#               no GPU passthrough into the container, so hashcat's whole
#               point - GPU speed - would not apply)
#   dnsutils    `dig` (target 6)
#   dnsrecon    DNS enumeration (target 6)
#   httpie      a readable JSON-first HTTP client (targets 12/13)
#   whois       domain/IP registration lookups, a common recon step
RUN apt-get update && apt-get install -y --no-install-recommends \
        nmap \
        ncat \
        tcpdump \
        tshark \
        sqlmap \
        jq \
        john \
        dnsutils \
        dnsrecon \
        httpie \
        whois \
    && rm -rf /var/lib/apt/lists/*

# ffuf: content/directory discovery (plan's "gobuster or ffuf" - ffuf chosen,
# one static Go binary, no JVM/Ruby runtime to also pin). Checksums from the
# release's own checksums.txt: https://github.com/ffuf/ffuf/releases/tag/v2.3.0
ARG FFUF_VERSION=2.3.0
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) arch="amd64"; sha256="b2a3c725fcb9da175159682f54d6e9149f2905b00d84d155e7efc5d599975ceb" ;; \
    arm64) arch="arm64"; sha256="e2d712615d53da797ee929006e41f2df5a7960a5353133db9c150ddaa22ae4e8" ;; \
    *) echo "Unsupported architecture for ffuf: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/ffuf.tar.gz \
      "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_${arch}.tar.gz"; \
    echo "${sha256}  /tmp/ffuf.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/ffuf.tar.gz -C /tmp ffuf; \
    install -m 0755 /tmp/ffuf /usr/local/bin/ffuf; \
    rm -f /tmp/ffuf.tar.gz /tmp/ffuf

# opa: policy evaluation (plan's "conftest/opa", for target 9 - lets a
# student run the same policy engine `cloud-policy-as-code` teaches against
# their own input). The static build has no libc dependency, matching this
# slim base. Checksums from the release's own .sha256 files:
# https://github.com/open-policy-agent/opa/releases/tag/v1.21.1
ARG OPA_VERSION=1.21.1
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) arch="amd64"; sha256="668506eb17a2eaa1fce6cc0d1f42ef85125d4ac5bda5fc74d1152d0c77145031" ;; \
    arm64) arch="arm64"; sha256="9a1f3625529c6f01240fe68286dde06aa0b23c5253da700ac48f4d943ff8a4de" ;; \
    *) echo "Unsupported architecture for opa: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/opa "https://github.com/open-policy-agent/opa/releases/download/v${OPA_VERSION}/opa_linux_${arch}_static"; \
    echo "${sha256}  /tmp/opa" | sha256sum -c -; \
    install -m 0755 /tmp/opa /usr/local/bin/opa; \
    rm -f /tmp/opa

# A small, generic path/name subset for ffuf-style discovery labs (plan
# §9's "a wordlist subset") - no lab-specific words, so it can't leak which
# target a given word is for. Referenced from lab-info/ffuf.md below.
COPY wordlist-common.txt /usr/local/share/wordlists/common.txt

# Lab Info library (plan §9, decision CTF-D16, phase CTF-P2b): the Linux
# primer plus one primer per tool above, reviewed for "mechanics, not
# exploits" (no injection strings, no reverse-shell one-liners, no cracked-
# hash walkthroughs, no CVE steps, no lab-specific hints). Same content for
# every CTF session pack, baked in here rather than mounted, since nothing
# about it varies per workshop.
#
# Seeded via /etc/skel so every account provision-account.sh creates (a
# student, a bot, or a reset rebuilding a home from /etc/skel) gets its own
# writable ~/lab-info copy for free, with no change to engine/ needed -
# provision-account.sh's useradd --create-home and its "cp -a /etc/skel/."
# reset path both already populate a new home from here. The facilitator
# (root) doesn't go through useradd, so its copy is seeded explicitly below.
#
# Also served read-only in the browser: compose.yml's ctf-lab-info (a stock
# Caddy mounting this same content/lab-info directory) plus this module's
# extensions.json card/route/admin tab (plan §9's "its own extensions.json
# card and matching /admin tab") - the two can't drift since both read from
# here.
COPY content/lab-info /etc/skel/lab-info
RUN cp -a /etc/skel/lab-info /root/lab-info

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
