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
attack_port_base="${CTF_ATTACK_PORT_BASE:-16000}"
attack_port_block="${CTF_ATTACK_PORT_BLOCK:-3}"

if ! getent hosts ctf-host >/dev/null 2>&1; then
  echo "ctf-range: ctf-host not resolvable (ctf_net not joined yet?); skipping firewall rules" >&2
  exit 0
fi
ctf_host_ip="$(getent hosts ctf-host | awk '{print $1; exit}')"

echo "Setting up per-account ctf-range target isolation (CTF_ISOLATION iptables chain)..." >&2

# Idempotent, same pattern as DOJO_ISOLATION in entrypoint.sh: flush instead
# of erroring on a re-run, only add the OUTPUT jump once.
iptables -N CTF_ISOLATION 2>/dev/null || iptables -F CTF_ISOLATION
iptables -C OUTPUT -j CTF_ISOLATION 2>/dev/null || iptables -A OUTPUT -j CTF_ISOLATION

# Root always needs this (readiness probes, this hook's own re-runs under a
# restart), same exception DOJO_ISOLATION makes.
iptables -A CTF_ISOLATION -p tcp -m owner --uid-owner 0 -d "$ctf_host_ip" -j ACCEPT

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"
  port=$((host_port_base + counter - 1))         # 0-based index, same as controller.py's Config.index
  attack_port_start=$((attack_port_base + (counter - 1) * attack_port_block))
  attack_port_end=$((attack_port_start + attack_port_block - 1))
  uid="$(id -u "$username" 2>/dev/null || true)"
  if [ -n "$uid" ]; then
    iptables -A CTF_ISOLATION -p tcp --dport "$port" -d "$ctf_host_ip" -m owner --uid-owner "$uid" -j ACCEPT
    iptables -A CTF_ISOLATION -p tcp --dport "$attack_port_start:$attack_port_end" -d "$ctf_host_ip" -m owner --uid-owner "$uid" -j ACCEPT
  fi
  counter=$((counter + 1))
done

# Default-deny catch-all for ctf_net traffic: must be the LAST rule, after
# every per-student ACCEPT above. Anything not already accepted - another
# student's port, a scan of the rest of ctf-host, anything else on ctf_net -
# falls through to this DROP. Traffic to any address OTHER than ctf-host on
# ctf_net is also dropped here (nothing else is meant to be reachable there).
iptables -A CTF_ISOLATION -d "$ctf_host_ip" -j DROP
