#!/bin/sh
# ctf-range start.d hook, run by the base web-terminal entrypoint as root
# after every account exists and after DOJO_ISOLATION is fully built (plan
# §4 "Terminal side", spikes CTF-S2/S3). Gives each student uid exactly one
# reachable address: ctf-host's own address on `ctf_net`, on the one port
# ctf-controller published that student's slot at (HOST_PORT_BASE + index,
# controller.py's Config). Everyone else's slot, and anything else on
# ctf_net, stays unreachable for that uid.
#
# This is the uid+port shape add_isolation_rule already uses in
# engine/web-terminal/entrypoint.sh, just a new chain and a remote address
# instead of loopback (students never get a second local listener here).
#
# Why no per-target network/SNAT (the plan's original S2/S3 sketch, written
# before CTF-D21): CTF-D21 replaced "one container per target on a shared
# ctf_net" with the boxed ctf-host dind - targets live INSIDE it, each
# reachable from outside only via its one published port on ctf-host's own
# address (docs/CTF-SPIKES.md S14). A student can never address another
# target directly (there is nothing to SNAT around; --icc=false in
# ctf-host/entrypoint.sh blocks slot-to-slot, and slots can make no NEW
# outbound connection at all), so per-uid isolation here only has to gate
# which of ctf-host's ports a uid's traffic may reach - no second mechanism
# needed. The per-target SNAT spiked in S14 is for slot-to-slot return
# traffic INSIDE ctf-host and is handled there, not here.
#
# CTF_HOST_PORT_BASE must match the same-named default in
# ctf-controller/controller.py (HOST_PORT_BASE) - module.env documents the
# pairing. STUDENT_COUNT/STUDENT_PREFIX are the same values the base
# entrypoint already used to provision accounts (roster order must match
# controller.py's Config.index exactly, or a uid's rule would point at a
# different student's slot).
#
# Also opens a BLOCK of CTF_ATTACK_PORT_BLOCK ports starting at
# CTF_ATTACK_PORT_BASE + index*block (plan §4 "Student-controlled targets",
# decision CTF-D20, widened for §7.3's nmap primer): the CTF-1..4 toggle's
# AttackManager publishes a student's live target as a small port BLOCK, not
# one port - the real app plus a fixed set of decoy ports (controller.py's
# Config.attack_ports(): ATTACK_PORT_BLOCK, DECOY_SSH_CONTAINER_PORT,
# DECOY_FTP_CONTAINER_PORT), so a student's `nmap` finds more than the one
# port they'll actually use, same as a HackTheBox box. The same per-uid rule
# shape applies to the whole block at once (one iptables range, not one rule
# per port). A student's attack slot being stopped most of the time, or a
# given target not using every decoy slot, doesn't need a conditional rule
# here - an ACCEPT for a port nothing is listening on yet is a no-op, and the
# rule is already in place the moment a container does listen there.
set -eu

student_count="${STUDENT_COUNT:-30}"
student_prefix="${STUDENT_PREFIX:-student}"
host_port_base="${CTF_HOST_PORT_BASE:-15000}"
# Per-target IP block (HackTheBox-style, 2026-10-07). ctf-host adds the
# addresses to its ctf_net interface; this hook ACCEPTs each student uid's
# own 4 IPs. Must match controller.py's ATTACK_IP_BASE_OCTET /
# ATTACK_IPS_PER_STUDENT and the ctf-host entrypoint's own layout.
attack_ip_base_octet="${CTF_ATTACK_IP_BASE_OCTET:-100}"
attack_ips_per_student="${CTF_ATTACK_IPS_PER_STUDENT:-4}"

# ctf-host is a boxed DinD daemon that now imports 10 baked image archives
# at its own start (customer-portal + its pinned deps base, plus the 8
# attack-ladder targets, CTF-1/CTF-2 — ~4-5 min observed live, 2026-10-06).
# web-terminal's start.d hooks run much earlier in compose's own startup
# (this container reaches "healthy" long before ctf-host does), so a
# one-shot `getent hosts` here raced and lost: ctf-host's container, and so
# its DNS entry on ctf_net, didn't exist yet at all, and the old single
# skip-and-exit-0 left this container permanently with NO isolation rules
# for ctf-host traffic at all - not "fails closed", just never ran (caught
# live: student02 could reach student01's attack slot with zero rules in
# place until this hook was re-run by hand). Retry instead of skip once;
# ctf-host coming up is a matter of when, not if.
tries=0
until getent hosts ctf-host >/dev/null 2>&1; do
  tries=$((tries + 1))
  if [ "$tries" -ge 180 ]; then
    echo "ctf-range: ctf-host still not resolvable after 180s; giving up" >&2
    exit 1
  fi
  sleep 1
done
ctf_host_ip="$(getent hosts ctf-host | awk '{print $1; exit}')"

echo "Setting up per-account ctf-range target isolation (CTF_ISOLATION iptables chain)..." >&2

# Idempotent, same pattern as DOJO_ISOLATION in entrypoint.sh: flush instead
# of erroring on a re-run, only add the OUTPUT jump once.
iptables -N CTF_ISOLATION 2>/dev/null || iptables -F CTF_ISOLATION
iptables -C OUTPUT -j CTF_ISOLATION 2>/dev/null || iptables -A OUTPUT -j CTF_ISOLATION

# Root always needs this (readiness probes, this hook's own re-runs under a
# restart), same exception DOJO_ISOLATION makes.
iptables -A CTF_ISOLATION -p tcp -m owner --uid-owner 0 -d "$ctf_host_ip" -j ACCEPT

# Pull the /24-ish prefix out of CTF_NET_SUBNET for the per-target IPs
# (ctf-host added them to its own eth1 inside this subnet; same assumption
# as the controller's ATTACK_SUBNET_PREFIX split).
attack_prefix=""
if [ -n "${CTF_NET_SUBNET:-}" ]; then
  attack_prefix="$(printf '%s' "$CTF_NET_SUBNET" | sed -E 's#\.[0-9]+/[0-9]+$##')."
fi

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"
  port=$((host_port_base + counter - 1))         # 0-based index, same as controller.py's Config.index
  uid="$(id -u "$username" 2>/dev/null || true)"
  if [ -n "$uid" ]; then
    # CTF-5 always-on slot: one port on ctf-host (reconcile path keeps the
    # port-block scheme; ctf-defend uses this).
    iptables -A CTF_ISOLATION -p tcp --dport "$port" -d "$ctf_host_ip" -m owner --uid-owner "$uid" -j ACCEPT
    # CTF-1..4 attack slots (2026-10-07): each student uid can reach their
    # own K reserved IPs on ctf_net, native target ports and all. ctf-host
    # added these addresses to its own eth1; the inner dockerd publishes
    # each slot bound to the specific IP for this (user, target). One range
    # rule per student instead of K rules.
    if [ -n "$attack_prefix" ]; then
      first=$((attack_ip_base_octet + (counter - 1) * attack_ips_per_student))
      last=$((first + attack_ips_per_student - 1))
      if [ "$last" -le 254 ]; then
        iptables -A CTF_ISOLATION -m iprange --dst-range "${attack_prefix}${first}-${attack_prefix}${last}" \
          -m owner --uid-owner "$uid" -j ACCEPT
      fi
    fi
  fi
  counter=$((counter + 1))
done

# Default-deny catch-all for ctf_net traffic: two rules, in this order, after
# every per-student ACCEPT above.
#
# 1) Anything landing on ctf-host that was not accepted by a per-uid rule
#    (another student's slot port, a scan of the rest of ctf-host's ports)
#    falls through to a targeted DROP.
# 2) Anything landing on ANY OTHER address inside ctf_net's subnet also
#    drops. The original comment here claimed the first rule did both; it
#    does not -- `-d $ctf_host_ip` only matches traffic to ctf-host, so
#    without this second rule a student uid could nmap attacker-bot, the
#    dev customer-portal and any other same-net member (2026-10-06 fix).
#    CTF_NET_SUBNET is set in compose.yml, pinned to the ipam.config.subnet
#    we also set there; empty = fall back to the per-ctf-host rule above
#    only, which keeps the old (looser) behaviour instead of a wrong catch.
#    Root is already past this chain by the per-uid ACCEPT at the top, and
#    anything on workshop_lab / ctf_ops is on a different interface so it
#    is unaffected here (output chain only).
iptables -A CTF_ISOLATION -d "$ctf_host_ip" -j DROP
if [ -n "${CTF_NET_SUBNET:-}" ]; then
  iptables -A CTF_ISOLATION -d "$CTF_NET_SUBNET" -j DROP
fi
