# Git Fundamentals — Azure DevOps Edition

Same Session 1 content as the [local Forgejo lab](../README.md), delivered
against an Azure Repos project instead of the self-hosted stack in
`engine/`. Nothing under `engine/` applies here — repo creation and access
are manual, in Azure DevOps.

**Status: content only.** These docs describe a complete delivery plan but
have not been re-verified against a live Azure DevOps project recently —
review [`azure-devops-setup-guide.md`](azure-devops-setup-guide.md) and
confirm the steps still match the current Azure DevOps UI before relying on
this path for a session.

## Materials

| Material | Purpose | Audience |
| -------- | ------- | -------- |
| [Azure DevOps Setup Guide](azure-devops-setup-guide.md) | Create the sample repo in Azure Repos, manage access | You, before the session |
| [Facilitator Guide](facilitator-guide.md) | Speaker notes, talking points, timing, troubleshooting | You |
| [Slide Outline](slide-outline.md) | Suggested slides + visuals for Part A | Build your deck here |
| [Pre-Work Checklist](pre-work-checklist.md) | Git/Azure DevOps setup, SSH/HTTPS test | Send to attendees 24h before |
| [Cheat Sheet](cheat-sheet.md) | One-page command/glossary reference | Print & distribute |
| [Materials Distribution Checklist](materials-distribution-checklist.md) | Prepare and distribute session materials | You |
| [Post-Session Feedback Survey](post-session-feedback-survey.md) | Collect attendee feedback | Attendees, after |
| [FAQ](faq.md) | Common Git/Azure Repos/recovery questions | Everyone |
| [Backup Slide Content](backup-slide-content.md) | Optional slides for questions/contingencies | Build in as needed |
| [Detailed Content Plan](session-01-plan.md) | Deep dive into concepts and workflow | Optional reference |
| [Lab Exercise Plan](workshop-01-lab-plan.md) | Step-by-step lab instructions | Attendees, Part B |
| [Sample Repo](sample-training-repo/) | Ready-to-clone starter repo | Upload to Azure Repos |

## Before session day

1. Read [azure-devops-setup-guide.md](azure-devops-setup-guide.md).
2. Create an Azure Repos repo and upload [`sample-training-repo/`](sample-training-repo/).
3. Clone it locally and verify clone/push/PR works.
4. Optionally set branch policies on `main`.
5. Fill in your org/project/repo URLs in [pre-work-checklist.md](pre-work-checklist.md) and send to attendees 24h before.
6. Add attendees to the Azure DevOps project.
7. Build the deck from [slide-outline.md](slide-outline.md); print [cheat-sheet.md](cheat-sheet.md).
8. Review [facilitator-guide.md](facilitator-guide.md) for timing and troubleshooting.
