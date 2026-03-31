# GitHub branch snapshots (local exports)

This document describes **every branch** currently on `origin` for [pbathuri/Claude_Hackathon](https://github.com/pbathuri/Claude_Hackathon), how they relate, and **which to use when**.

On-disk copies of each branch’s **tracked files** (no `node_modules`, no `.git`) live under:

`branch_exports/<sanitized-branch-name>/`

Branch names with `/` are flattened (e.g. `integrate/twilio-kg-claude` → `integrate-twilio-kg-claude`).

## How these folders were produced

1. `git fetch origin --prune`
2. For each `origin/<branch>`, `git archive` → extract to `branch_exports/...`

This is **read-only** for your working tree: your current checkout and branch are unchanged.

To **refresh** exports after new pushes:

```bash
chmod +x scripts/export-github-branches.sh   # once
./scripts/export-github-branches.sh
```

`branch_exports/` is listed in `.gitignore` so large duplicate trees are not committed by accident. Remove that line only if you intentionally want snapshots in git.

---

## Branch inventory (as of last export)

| Branch | Tip commit (short) | Last commit date (author) | One-line purpose |
|--------|-------------------|---------------------------|------------------|
| **main** | `9eddedc` | 2026-03-29 | Default line of development: voice/Twilio fixes, async Claude, Gather redirects, portal alignment, ops/docs. |
| **production-hardening** | `9008799` | 2026-03-28 | Portal/backend alignment with canonical case statuses (`CaseStatusType`); “hardening” baseline before later main-only commits. |
| **integrate/twilio-kg-claude** | `f7b3bc9` | 2026-03-28 | Twilio voice merged with production-hardening gather fixes; explicit Claude + KG wiring in the voice path. |
| **updated-call-fixes** | `beade13` | 2026-03-29 | Diverged WIP: Dockerfile, requirements root, doctor-portal-oriented fixes; **not** rebased on latest main. |
| **caller-api** | `d1b2428` | 2026-03-28 | Minimal early tree: small `src/` Python prototype + SDD PDF/DOCX; **not** the full monorepo. |

---

## Versions & stack signals (not every branch has the same files)

Where the **doctor portal** exists, `doctor-portal/package.json` is typically **version `0.1.0`**, **Next.js 14**, **React 18**, **Node ≥ 18** — differences between branches are **features and pages**, not usually the semver in `package.json`.

Where **`backend/requirements.txt`** exists (via root `-r backend/requirements.txt`), pinned examples include **FastAPI 0.115.x**, **Anthropic**, **Twilio**, **Alembic**, **SQLAlchemy 2.x** — again, **branch diffs** matter more than a single “version number” for the whole product.

**Python**: branches that include `.python-version` commonly pin **3.11** (check the file inside each export if needed).

---

## Relationship to `main` (high level)

Approximate `git rev-list --left-right --count origin/main...origin/<branch>` interpretation:

| Compared branch | Commits on `main` not in branch | Commits on branch not in `main` |
|-----------------|--------------------------------|-----------------------------------|
| production-hardening | many | 0 (ancestor line; `main` has moved forward) |
| integrate/twilio-kg-claude | many | 0 |
| caller-api | many | 0 |
| updated-call-fixes | several | **3** (branch has **unique** commits; also **missing** many `main` commits) |

So: **`main` is ahead** of most named branches. **`updated-call-fixes` is the odd one out**: it has a few commits not on `main` but lacks most of the recent voice/portal work on `main`.

---

## Pros / cons by branch

### `main` — **recommended default**

- **Pros**: Richest tree (backend, doctor portal, docs, Docker, CI, archives, integration guides); latest Twilio Gather/silence handling and voice workflow work; best match to “what we run and deploy now.”
- **Cons**: Moves quickly; you need discipline (tests, env vars) when pulling.
- **Use for**: Day-to-day development, demos, deployment source of truth.

### `production-hardening`

- **Pros**: Clear snapshot focused on **canonical statuses** and portal contract alignment; useful to compare “before/after” UI state names.
- **Cons**: **Behind `main`** by a large number of commits; missing newer voice, portal, and ops changes.
- **Use for**: Historical comparison, auditing the “hardening” milestone, not as primary deploy branch unless you explicitly branch from it again.

### `integrate/twilio-kg-claude`

- **Pros**: Documents the **integration moment** where Twilio + Claude + KG were wired together with gather fixes; good narrative for “how voice met the graph.”
- **Cons**: Superseded by **`main`** for ongoing work; no unique tip commits vs continuing on `main`.
- **Use for**: Understanding integration history; avoid as long-lived fork unless you merge `main` into it.

### `updated-call-fixes`

- **Pros**: Carries **branch-only** work (e.g. Dockerfile emphasis, portal-related fixes in its timeline) that might be worth **cherry-picking** if not already on `main`.
- **Cons**: **Diverged** — missing most recent `main` fixes; **not** a safe drop-in replacement for current production behavior without a merge/rebase review.
- **Use for**: Mining specific commits; **not** recommended as primary branch without reconciliation with `main`.

### `caller-api`

- **Pros**: Small, easy to read; SDD artifacts preserved; early `src/` entry points for experiments.
- **Cons**: **Not** the full platform (no monorepo backend/portal as shipped later); mostly archival.
- **Use for**: Reference only; do not confuse with current API surface.

---

## Which branch is “better”?

There is no universal answer:

- **For shipping and integrating today**: **`main`** is the strongest default.
- **For comparing “hardening era” vs “latest”**: compare **`production-hardening`** (or **`integrate/twilio-kg-claude`**) **to** **`main`** with `git log` / `git diff`, not by guessing from names alone.
- **For recovering odd fixes**: inspect **`updated-call-fixes`** and **cherry-pick** onto `main` after review.

---

## Folder map (local exports)

| Directory under `branch_exports/` | Remote branch |
|-----------------------------------|---------------|
| `main/` | `origin/main` |
| `production-hardening/` | `origin/production-hardening` |
| `integrate-twilio-kg-claude/` | `origin/integrate/twilio-kg-claude` |
| `updated-call-fixes/` | `origin/updated-call-fixes` |
| `caller-api/` | `origin/caller-api` |

---

## Safety notes

- Exports contain **no git history** — only file trees. Use `git checkout <branch>` or `git worktree` when you need history, bisect, or blame.
- Do not paste **secrets** into tracked docs; this file intentionally references only **public** repo metadata.
- Regenerating `branch_exports/` **overwrites** that directory; copy anything you edited inside it before re-running the script.
