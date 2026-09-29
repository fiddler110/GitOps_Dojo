# dns-gate module: each account's own PowerDNS API key (start.d/50-dns-key.sh)
# in $DNS_API_KEY for every shell. Demo bots start before the hook runs, so
# their steps.sh reads the file itself.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY start.d/50-dns-key.sh /etc/dojo/start.d/50-dns-key.sh
RUN set -eux; \
    chmod 0755 /etc/dojo/start.d/50-dns-key.sh; \
    snippet='if [ -r "$HOME/.config/dojo/dns-api-key" ]; then export DNS_API_KEY="$(cat "$HOME/.config/dojo/dns-api-key")"; fi'; \
    printf '\n# dns-gate module: this account'"'"'s own key for http://dns-api:8081\n%s\n' "$snippet" >> /etc/zsh/zshenv; \
    printf '%s\n' "$snippet" > /etc/profile.d/dns-gate.sh
