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

## More Info:

# CTF Challenge: SQL Injection Authentication Bypass

This challenge features a simple administrative login panel backed by an SQLite database. The backend authentication query is written insecurely, allowing players to perform an SQL Injection (SQLi) attack to short-circuit the login logic and retrieve the flag without knowing the password.

## 📁 Directory Structure

To set up this challenge, create a directory on your system with the following structure:

```text
sqli-challenge/
├── Dockerfile
├── flag.txt
└── src/
    └── index.php
```

---

## 📄 1. The Flag (`flag.txt`)

Create a file named `flag.txt` inside your main folder and place your target flag format inside it.

```text
CTF{sqli_auth_bypass_master_2026}
```

---

## 📄 2. The Vulnerable Backend Script (`src/index.php`)

Create a folder named `src`, and inside it, save the following code as `index.php`. This contains both the HTML frontend form and the vulnerable SQLite database logic.

```php
<?php
// 1. Setup an in-memory SQLite Database for speed and isolation
$db = new SQLite3(':memory:');

// 2. Create a mock users table and insert an admin account
$db->exec("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT);");
$db->exec("INSERT INTO users (username, password) VALUES ('admin', 'SuperSecretComplexPassword123!');");

$message = "";
$flag = "";

// 3. Process the login form when submitted
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = $_POST['username'] ?? '';
    $password = $_POST['password'] ?? '';

    // VULNERABILITY: Direct string concatenation allows input payload to alter the SQL logic
    $query = "SELECT * FROM users WHERE username = '" . $username . "' AND password = '" . $password . "'";

    try {
        $result = $db->query($query);
        $row = $result ? $result->fetchArray(SQLITE3_ASSOC) : false;

        if ($row && $row['username'] === 'admin') {
            // Success: Read the flag file from the container file system
            $flag = file_get_contents('/var/www/flag.txt');
            $message = "<div class='alert success'>Welcome back, Administrator!</div>";
        } else {
            $message = "<div class='alert error'>Invalid username or password.</div>";
        }
    } catch (Exception $e) {
        // Show SQL error messages to help the user debug their exploit syntax (Common in CTFs)
        $message = "<div class='alert error'>Database Error: " . htmlspecialchars($e->getMessage()) . "</div>";
    }
}
?>

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Portal Login</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a1a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-container { background-color: #262626; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 350px; border: 1px solid #333; }
        h2 { text-align: center; margin-bottom: 24px; color: #00ff66; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #aaa; font-size: 14px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #444; background-color: #333; color: #fff; border-radius: 4px; box-sizing: border-box; }
        input:focus { border-color: #00ff66; outline: none; }
        button { width: 100%; padding: 10px; background-color: #00ff66; border: none; color: #1a1a1a; font-weight: bold; border-radius: 4px; cursor: pointer; font-size: 16px; transition: background 0.2s; }
        button:hover { background-color: #00cc52; }
        .alert { padding: 10px; border-radius: 4px; margin-bottom: 15px; font-size: 14px; text-align: center; }
        .error { background-color: #ff3333; color: white; }
        .success { background-color: #00ff66; color: #1a1a1a; font-weight: bold; word-break: break-all; }
        .flag-box { margin-top: 15px; padding: 10px; background: #111; border: 1px dashed #00ff66; color: #00ff66; font-family: monospace; text-align: center; }
    </style>
</head>
<body>

<div class="login-container">
    <h2>Secure Admin Login</h2>
    <?php echo $message; ?>

    <?php if (!empty($flag)): ?>
        <div class="flag-box">
            <strong>FLAG FOUND:</strong><br>
            <?php echo htmlspecialchars($flag); ?>
        </div>
    <?php else: ?>
        <form method="POST" action="">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autocomplete="off">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
    <?php endif; ?>
</div>

</body>
</html>
```

---

## 📄 3. The Infrastructure Configuration (`Dockerfile`)

Create a file named `Dockerfile` in the parent directory. This builds an isolated PHP 8 container web server running Apache and sets secure read-only permissions for the flag layout.

```dockerfile
FROM php:8.2-apache

# 1. Install SQLite3 system dependencies and PHP extensions
RUN apt-get update && apt-get install -y libsqlite3-dev && \
    docker-php-ext-install sqlite3 && \
    apt-get clean && rm -rf /var/lib/lists/*

# 2. Copy the web source files to the web server root directory
COPY src/ /var/www/html/

# 3. Securely place the flag outside the public web root directory
COPY flag.txt /var/www/flag.txt

# 4. Strict permission locking: Web directory belongs to root, readable by www-data
RUN chown -R root:www-data /var/www/html /var/www/flag.txt && \
    chmod 755 /var/www/html && \
    chmod 644 /var/www/html/index.php && \
    chmod 640 /var/www/flag.txt

# 5. Expose default HTTP traffic port
EXPOSE 80
```

---

## 🚀 How to Run and Test Locally

### 1. Build the container

Open your terminal inside the `sqli-challenge/` directory and build the Docker image:

```bash
docker build -t ctf-sqli-login .
```

### 2. Launch the container

Run the built container and forward your local port `8080` to the container's web port `80`:

```bash
docker run -d -p 8080:80 --name ctf-sqli-instance ctf-sqli-login
```

### 3. Exploit It!

1. Open your web browser and navigate to `http://localhost:8080`.
2. In the **Username** field, type the following SQL injection authentication bypass payload:
    ```text
    admin' OR 1=1 --
    ```
3. Type anything (or nothing) into the **Password** field.
4. Click **Login**. The database query will bypass password verification and print out your flag!

# 🚀 Deep Dive: 10 Legendary Hack The Box Machines & Top-Tier Write-Ups

This curated analysis covers **10 of the most culturally significant, highly rated Hack The Box (HTB) machines**. These boxes are celebrated because they teach core, realistic penetration testing methodologies that are perfectly reproducible for custom CTF challenge architecture.

The gold standard for write-ups in the cybersecurity community belongs to **[IppSec](https://ippsec.rocks)** (the authority on comprehensive video breakdowns and system setup logic) and **[0xdf](https://gitlab.io)** (the authority on meticulous, text-based code analysis and reproduction steps).

---

### 1. Lame (The Ultimate Classic Starter)

- **OS:** Linux 🐧 | **Difficulty:** Easy
- **Core Vulnerability:** Remote Code Execution (RCE) via Samba 3.0.20 (`CVE-2007-2447` / "Username map script").
- **Why it’s famous:** It is machine ID #1 on Hack The Box. It fundamentally demonstrates how software configuration flaws allow unauthenticated remote root access directly.
- **The Best Write-Up:** **[0xdf's Lame Walkthrough](https://gitlab.io2018/08/17/htb-lame.html)**
- **Value for CTF Creators:** 0xdf explains exactly how Samba processes input data into a shell execution string, providing an architectural blueprint for a simple input-injection box.

### 2. Shocker (The CGI Script Breaker)

- **OS:** Linux 🐧 | **Difficulty:** Easy
- **Core Vulnerability:** Shellshock (`CVE-2014-6271`) inside an Apache Common Gateway Interface (CGI) script.
- **Why it’s famous:** It teaches directory brute-forcing targeting file extensions (`.sh`, `.cgi`) and exploiting environment variables.
- **The Best Write-Up:** **[IppSec's Shocker Video on YouTube](https://youtube.com)**
- **Value for CTF Creators:** IppSec demonstrates how to find hidden configuration roots via tools like `Gobuster` and explains the precise layout needed to build a vulnerable CGI shell script container.

### 3. Jerry (The Apache Tomcat Default Trap)

- **OS:** Windows 🪟 | **Difficulty:** Easy
- **Core Vulnerability:** Exploiting default administrative credentials (`tomcat:s3cret`) on an Apache Tomcat Manager panel.
- **Why it’s famous:** It represents a common real-world enterprise mistake: leaving default credentials active on internal management ports.
- **The Best Write-Up:** **[0xdf's Jerry Walkthrough](https://gitlab.io2018/12/15/htb-jerry.html)**
- **Value for CTF Creators:** This write-up shows how a user can bundle a reverse shell into a `.war` (Web Application Archive) file and upload it via the manager GUI to execute system commands.

### 4. Cap (The Network Inspection Box)

- **OS:** Linux 🐧 | **Difficulty:** Easy
- **Core Vulnerability:** Insecure Direct Object Reference (IDOR) to access raw packet capture (`.pcap`) logs containing cleartext FTP credentials.
- **Why it’s famous:** It seamlessly merges web application logic flaws with network forensic captures.
- **The Best Write-Up:** **[0xdf's Cap Walkthrough](https://gitlab.io2021/07/03/htb-cap.html)**
- **Value for CTF Creators:** Explains the IDOR flaw path `/data/0` and shows how a custom backend Python script with poor Linux Capabilities (`cap_setuid`) allows immediate privilege escalation.

### 5. EternalLoop (The Nested Archival Forensic)

- **OS:** Linux 🐧 | **Difficulty:** Easy (Challenge-style box)
- **Core Vulnerability:** Scripted nesting of zip files requiring password-cracking at each iteration.
- **Why it’s famous:** It is a pure automation test. Humans cannot solve it manually; players must write a Python loop script to break open hundreds of consecutive archives.
- **The Best Write-Up:** **[0xdf's Challenge Writeups Directory](https://gitlab.io)**
- **Value for CTF Creators:** Teaches you how to write a quick loop script utilizing `unzip` and `fcrackzip` to process dynamic passkeys sequentially.

### 6. Active (The Active Directory Foundation)

- **OS:** Windows 🪟 | **Difficulty:** Easy
- **Core Vulnerability:** Kerberoasting and Server Message Block (SMB) share enumeration.
- **Why it’s famous:** It is widely considered the absolute best introductory machine for understanding Windows Active Directory exploitation fundamentals.
- **The Best Write-Up:** **[IppSec's Active Video Walkthrough](https://youtube.com)**
- **Value for CTF Creators:** IppSec explicitly breaks down how Active Directory service principal accounts store encrypted tickets (`TGS-REP`) and how to crack them using `hashcat` offline.

### 7. Forest (Active Directory BloodHound Pivoting)

- **OS:** Windows 🪟 | **Difficulty:** Easy/Medium
- **Core Vulnerability:** AS-REP Roasting and abusing specific domain group privilege delegations.
- **Why it’s famous:** It transitions players from singular credential attacks to graphing complex AD delegation abuse paths using **BloodHound**.
- **The Best Write-Up:** **[0xdf's Forest Machine Analysis](https://gitlab.io2020/02/01/htb-forest.html)**
- **Value for CTF Creators:** Gives you the perfect blueprint for creating AD security-group relationships (like nesting a user inside "Account Operators") to create a structured chain of escalation.

### 8. Jarvis (The Multi-Stage Injection Challenge)

- **OS:** Linux 🐧 | **Difficulty:** Medium
- **Core Vulnerability:** SQL Injection to Web Shell, followed by custom system script hijacking.
- **Why it’s famous:** It forces the player to seamlessly tie together web exploitation, database pivoting, and Linux permission manipulation.
- **The Best Write-Up:** **[0xdf's Jarvis Walkthrough](https://gitlab.io2019/11/02/htb-jarvis.html)**
- **Value for CTF Creators:** Explains the complete pipeline from using `sqlmap` to gain interactive command shells, to searching local crontabs and custom binary hooks.

### 9. Nibbles (The Admin Portal Misdirection)

- **OS:** Linux 🐧 | **Difficulty:** Easy
- **Core Vulnerability:** Administrative directory disclosure leading to file upload execution via a vulnerable Nibbleblog plugin.
- **Why it’s famous:** It is the official machine used in the **OffSec OSCP PEN-200** training materials and certifications to practice foundational enumeration.
- **The Best Write-Up:** **[0xdf's Nibbles Box Walkthrough](https://gitlab.io2018/06/30/htb-nibbles.html)**
- **Value for CTF Creators:** Showcases how directory discovery reveals configuration pathways, and provides a clear guide on leveraging loose script structures for privilege escalation.

### 10. Netmon (The Network Management Leak)

- **OS:** Windows 🪟 | **Difficulty:** Easy
- **Core Vulnerability:** Exposed directory path parameters and cleartext credential caching on a PRTG Network Monitor system.
- **Why it’s famous:** It highlights third-party monitoring application flaws and demonstrates how software configuration backups often accidentally leak domain administrative passwords.
- **The Best Write-Up:** **[IppSec's Netmon Video Guide](https://youtube.com)**
- **Value for CTF Creators:** IppSec demonstrates searching configuration files (`.dat`, `.xml`) inside Windows program folders, finding previous master passwords, and applying clever variations to access high-tier APIs.
