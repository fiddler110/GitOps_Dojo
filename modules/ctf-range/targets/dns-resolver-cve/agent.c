/* dns-resolver-cve — the "internal service agent" the attack targets.
 *
 * Statically linked against uClibc-ng 1.0.39 (via the Bootlin cross-toolchain,
 * see ctf-host/Dockerfile's `dns-resolver-cve-agent-build` stage), so this
 * really is the libc whose stub resolver carries CVE-2022-30295 (predictable
 * monotonically-increasing DNS transaction IDs). Empirically confirmed on
 * 2026-10-06 (docs/CTF-SPIKES.md "Target 6" addendum): 20 consecutive
 * getaddrinfo() calls emitted TXIDs 2, 3, 4, ..., 21 — strictly +1 each query.
 *
 * The agent is a long-running checker: every CHECKIN_SECONDS it resolves
 * vault.svc.internal and connects to the resulting IP on port VAULT_PORT, then
 * sends its service token as a Bearer header. If the resolver returns 127.0.0.1
 * (the normal case) it reaches the real vault inside this container; if the
 * answer gets spoofed to 127.0.0.2 (the on-box "attacker's capture point", see
 * targets/dns-resolver-cve/app.py's module docstring) the token lands in the
 * attacker's receiver instead -- credential capture, exactly as the plan calls
 * for ("the spoofed answer makes the agent connect to the attacker and hand
 * over its service token", CTF-WORKSHOP-PLAN.md §7.3 row 6).
 *
 * Why we hand-set _res here instead of trusting /etc/resolv.conf: the slot
 * container's /etc/resolv.conf is written by the inner dockerd to point at
 * its embedded 127.0.0.11 resolver, which this lab never reaches; and the slot
 * runs non-root with CapDrop ALL (ctf-controller/docker_api.py's
 * build_create_request -- a central property the controller must not weaken),
 * so the DNS answerer in app.py cannot bind the privileged port 53. We
 * initialise the resolver state and then overwrite the one nameserver entry
 * with the unprivileged in-container 127.0.0.1:5353 the answerer DOES bind,
 * before every lookup. getaddrinfo() in uClibc 1.0.39 goes through the same
 * __dns_lookup path as res_query, so the TXID behaviour is identical — this
 * is still a real uClibc stub resolution, with the real predictable-TXID
 * emission the CVE is about, not a hand-rolled wire-format forgery.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <resolv.h>

static const char *getenv_default(const char *name, const char *dflt) {
    const char *v = getenv(name);
    return (v && *v) ? v : dflt;
}

static void set_nameserver(const char *addr, int port) {
    /* uClibc's getaddrinfo path reads _res (the global resolver state) on
     * every lookup, so overwriting the first nameserver entry after res_init
     * is enough to steer every subsequent lookup. */
    res_init();
    _res.nscount = 1;
    _res.nsaddr_list[0].sin_family = AF_INET;
    _res.nsaddr_list[0].sin_addr.s_addr = inet_addr(addr);
    _res.nsaddr_list[0].sin_port = htons((unsigned short)port);
    _res.retrans = 2;   /* seconds before a lookup is retried */
    _res.retry = 2;     /* max retries */
}

static int send_checkin(const char *ip, int port, const char *token) {
    struct sockaddr_in sa = { 0 };
    sa.sin_family = AF_INET;
    sa.sin_port = htons((unsigned short)port);
    if (inet_aton(ip, &sa.sin_addr) == 0) return -1;

    int s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;

    struct timeval tv = { .tv_sec = 3, .tv_usec = 0 };
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    if (connect(s, (struct sockaddr *)&sa, sizeof(sa)) != 0) {
        close(s);
        return -1;
    }

    /* Minimal HTTP/1.1 POST — the vault receiver and the attacker receiver
     * both answer the same shape (see app.py). We send the token as a Bearer
     * header, which is the credential-capture value if this call ever lands
     * at an address other than the real vault. */
    char buf[1024];
    int n = snprintf(buf, sizeof(buf),
        "POST /checkin HTTP/1.1\r\n"
        "Host: vault.svc.internal\r\n"
        "Authorization: Bearer %s\r\n"
        "User-Agent: dns-resolver-cve-agent/1\r\n"
        "Content-Length: 0\r\n"
        "Connection: close\r\n"
        "\r\n", token);
    if (n <= 0 || n >= (int)sizeof(buf)) { close(s); return -1; }
    ssize_t w = send(s, buf, (size_t)n, 0);
    char resp[256];
    (void)recv(s, resp, sizeof(resp), 0);  /* drain, don't care */
    close(s);
    return (w == n) ? 0 : -1;
}

int main(void) {
    const char *ns_addr    = getenv_default("AGENT_NS_ADDR",    "127.0.0.1");
    int ns_port            = atoi(getenv_default("AGENT_NS_PORT",   "5353"));
    const char *vault_name = getenv_default("AGENT_VAULT_NAME", "vault.svc.internal");
    int vault_port         = atoi(getenv_default("AGENT_VAULT_PORT", "9000"));
    int period             = atoi(getenv_default("AGENT_PERIOD_SECONDS", "2"));
    const char *token      = getenv_default("CTF_TARGET_TOKEN", "flag{dns-resolver-cve-token-dev}");
    if (period < 1) period = 1;

    set_nameserver(ns_addr, ns_port);

    /* First-run announcement -- flushed, so the slot's `docker logs` carries
     * the lab's own evidence that the real uClibc stub is in the loop. */
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("dns-resolver-cve-agent: ns=%s:%d name=%s vault_port=%d period=%ds\n",
           ns_addr, ns_port, vault_name, vault_port, period);

    struct addrinfo hints = { 0 }, *res = NULL;
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;

    unsigned long iter = 0;
    for (;;) {
        res = NULL;
        int rc = getaddrinfo(vault_name, NULL, &hints, &res);
        if (rc == 0 && res) {
            struct sockaddr_in *sin = (struct sockaddr_in *)res->ai_addr;
            char ip[INET_ADDRSTRLEN] = { 0 };
            inet_ntop(AF_INET, &sin->sin_addr, ip, sizeof(ip));
            int ok = send_checkin(ip, vault_port, token);
            printf("iter=%lu resolved=%s checkin=%s\n", iter, ip, ok == 0 ? "ok" : "fail");
            freeaddrinfo(res);
        } else {
            printf("iter=%lu resolve_rc=%d (%s)\n", iter, rc, gai_strerror(rc));
        }
        iter++;
        sleep((unsigned)period);
    }
    return 0;
}
