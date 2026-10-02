# 🌿 Topiary

**A micro-sculpted, air-gapped infrastructure hypervisor and hands-on playground.**

Topiary runs short-lived, deeply immersive workshops where engineers do the real work in a meticulously curated environment. Students push commits, watch CI orchestrate dynamic DNS changes, provision TLS certificates from an internal ACME authority, and deploy containers into a private, mock public cloud that real-world infrastructure providers can interact with natively. 

Every exercise is sculpted to strip away external noise, providing a direct, physical understanding of complex enterprise workflows. At the end of a session, `./run.sh stop` prunes the environment, removing it completely without a trace.

---

## 🧱 The Walled Garden Architecture

Topiary is designed from the ground up as a **Walled Garden**. It operates on the absolute belief that the best way to master production infrastructure is to break it, reshape it, and observe the failure modes firsthand. To make this educational model viable for enterprises, Topiary builds a protective, highly secure perimeter around the student, ensuring that **a mistake remains a lesson and never becomes an incident.**

This walled garden is engineered through three rigid architectural boundaries:

*   **Zone 3 Containment:** High-risk student actions, single-use CI runner pools, and privileged internal daemons are permanently isolated on distinct internal network namespaces with **zero route to the internet** or the outside host network. 
*   **Kernel-Level Tenant Isolation:** Topiary does not trust software-level user claims. All students share a single web-terminal container network namespace, but the Linux kernel strictly separates them using independent UIDs, locked password vectors, `0700` home directories, and custom `iptables` owner-match routing to isolate student IDEs and terminal ports.
*   **Zero-Trust Upstream Headers:** A single exposed entry point—the Caddy gateway—manages authentication. Every upstream communication must pass a constant-time `X-Gateway-Token` and `X-Auth-User` verification. Direct API spoofing from inside a terminal is rejected at the packet level.

---

## 🛡️ Rugged Security & Enterprise DevOps Utility

While Topiary functions as an educational playground, it is built with the rigor of mission-critical enterprise software. It addresses the realities of massive corporate compliance, air-gapped training facilities, and zero-trust policies out of the box:

*   **100% Self-Contained and Offline:** Once the base images are built, Topiary requires no external internet connection, no SaaS licensing, and no cloud provider accounts. Every CLI tool, configuration file, and provider binary is baked natively into the engine image, pinned to exact versions, and verified against sha256 checksums.
*   **Engineered Against Threat Models:** Topiary features an active, continuously audited threat model framework (remediating over 15 distinct container-escape and cross-tenant vulnerability vectors). Realism is pushed to the limit with advanced labs detailing secrets leakage scanning (`gitleaks`), encrypted repo management (`sops`), and workload identity integration (`OpenBao`).
*   **Deterministic Simulation Control:** Facilitators govern the space via a secure `/admin` workspace featuring live-updating multi-tenant terminal rosters, full OpenBao request audit logs, and autoscale controls for single-use single-job ephemeral runners.
*   **Gamified Progress Validation:** To drive engagement, Topiary tracks student advancement through cryptographic verification and local achievements, validating that workflows are built to correct form rather than just blindly executed.

---

## 🧭 The Plot Library (Workshops)

Topiary houses an ordered learning path where each lab structurally roots itself into the skills mastered in the previous one:

1.  **Git Fundamentals:** Internalizing the physical branch, commit, push, and conflict-resolution routines.
2.  **DNS as Code:** Driving live PowerDNS servers via `dnscontrol` through pull-request CI automation.
3.  **Certificate Autorenewal:** Forcing 5-minute automated ACME certificate loops over custom private CAs.
4.  **OpenTofu Basics:** Navigating real container deployments, quota policies, and state drift against **Topiary Cloud**.
5.  **Vault Fundamentals:** Eliminating static secrets using dynamic Postgres credentials, single-use runner OIDC logins, and workload identities.
