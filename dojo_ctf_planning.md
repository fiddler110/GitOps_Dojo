# GitOps Dojo CTF Integration Planning Blueprint

This document outlines the architecture, layout, and configuration strategies for integrating a **Boot2Root / Attack-Defend** style Capture The Flag (CTF) environment as a modular workshop plug-in within the **GitOps Dojo** platform.

---

## 1. Architectural Strategy

Instead of a shared platform where all competitors target a single system, the GitOps Dojo architecture allows for **isolated sandbox CTFs**. Every student gets a dedicated, isolated pair of containers containing an **Attack Box** (their web terminal) and a **Target Box** (the vulnerable system).

### High-Level Network Layout

```text
┌────────────────────────────────────────────────────────┐
│             STUDENT WORKSPACE CONTAINER                │
│                                                        │
│  ┌─────────────────┐            ┌──────────────────┐   │
│  │  Attack Box     │  Isolated  │  Target Box      │   │
│  │  (Terminal)     │───────────►│  (Vulnerable)    │   │
│  │  10.99.0.10     │  Network   │  10.99.0.5       │   │
│  └─────────────────┘            └──────────────────┘   │
└────────────────────────────────────────────────────────┘
```

### Core Design Rules

1. **Zero-Install:** Students use the built-in web terminal (`ttyd` + `tmux`) handled through Caddy.
2. **Network Isolation:** The network between the Attack Box and Target Box is completely internal (`internal: true`). The target has no link to the outside internet, the Caddy gateway, or neighboring students.
3. **Pluggable Targets:** The infrastructure components remain static. Swapping the entire CTF challenge requires changing only a single variable pointing to a different Target Box image.

---

## 2. Shared Workshop Template Configuration

To implement this, you will create a reusable workshop structure under the `workshops/` directory (e.g., `workshops/ctf-template/`).

### `workshop.env`

This file pins the toolsets for the attack box and keeps the target system modular.

```env
# The frontend terminal interface pre-loaded with penetration testing utilities
TERMINAL_IMAGE="ctf-attack-box:latest"

# The modular variable defining the target challenge instance
TARGET_CHALLENGE_IMAGE="ctf-target-knife:latest"

# Enable Dojo's internal routing orchestration module
MODULES="student-isolated-network"
```

### `extensions.json`

Renders the navigation cards on the student's browser dashboard.

```json
{
    "cards": [
        {
            "title": "CTF Challenge Guide",
            "description": "Read the instructions, hints, and learn your targets.",
            "url": "/guide/"
        },
        {
            "title": "Attack Terminal",
            "description": "Open your secure web terminal to exploit the target machine.",
            "url": "/terminal/"
        }
    ]
}
```

### `docker-compose.override.yml`

This compose snippet handles launching the paired sandbox environment for each student workspace.

```yaml
version: "3.8"

services:
    # The Student's Attack Terminal
    terminal:
        image: ${TERMINAL_IMAGE}
        networks:
            ctf_isolated_link:
                ipv4_address: 10.99.0.10
        environment:
            - TARGET_IP=10.99.0.5

    # The Target Box (Only this service container image shifts per challenge)
    target-box:
        image: ${TARGET_CHALLENGE_IMAGE}
        hostname: target-machine
        networks:
            ctf_isolated_link:
                ipv4_address: 10.99.0.5
        # Dojo Hardening: Read-only storage prevents persistent defacement
        read_only: true
        tmpfs:
            - /tmp
            - /run
        deploy:
            resources:
                limits:
                    cpus: "0.25"
                    memory: 128M

networks:
    ctf_isolated_link:
        internal: true
        ipam:
            config:
                - subnet: 10.99.0.0/24
```

---

## 3. Challenge Blueprint Matrix (Hack The Box Inspired)

By sharing the structure above, you can build multiple CTF workshops simply by shifting the underlying vulnerability configuration of the `TARGET_CHALLENGE_IMAGE`.

| Lab Challenge Name  | Foothold Objective (User Flag)                                                                                                        | Privilege Escalation (Root Flag)                                                                                                   | Skill Concepts Taught                                            |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------- |
| **"Cap" Style**     | **IDOR / Traffic Leak:** Web dashboard allows downloading arbitrary packet captures (`.pcap`) leaking plain-text service credentials. | **Linux Capabilities:** Exploiting custom binary permissions (like python/perl with `cap_setuid`) to read file flags.              | Web exploration, pcap analysis, binary enumeration.              |
| **"Knife" Style**   | **RCE Vulnerability:** Triggering an unpatched or backdoored web runtime framework capability to force a reverse shell.               | **Sudo Abuse (GTFOBins):** The user can run an application natively via `sudo` without a password, pivoting to an escape sequence. | Reverse shell handling, `sudo -l` auditing, GTFOBins navigation. |
| **"Unified" Style** | **Injection Flaws:** Exploiting injection vulnerabilities (like Log4j or Command Injection) inside an app panel.                      | **Credential Splunking:** Excavating exposed configuration files or application logs left behind by a careless administrator.      | Log parsing, post-exploitation enumeration, supply chain bugs.   |

---

## 4. Student & Flag Validation Flow

1. **The Foothold Phase:** The student boots their terminal, runs `nmap 10.99.0.5`, discovers open ports, and compromises the web utility. Reading `/home/user/user.txt` provides their first flag.
2. **The Privilege Escalation Phase:** They explore the target's operating system environment to elevate their access to `root` status. Reading `/root/root.txt` grants the final flag.
3. **Validation Options:**
    - **Local Validation (Dojo Style):** A native binary CLI tool (e.g., `submit-flag`) baked inside the user's workspace tracks validation internally and signals completion statuses directly up to the supervisor's `/admin` panel.
    - **Global Dashboard Registration:** A centralized, global `ctfd` instance is deployed within the main root compose stack, allowing students to access a shared scoreboard via a standard browser tab.
