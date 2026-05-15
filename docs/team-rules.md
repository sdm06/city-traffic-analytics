# Team Collaboration Rules

Practical rules that keep the repo clean and the team conflict-free.

---

## 👥 Who Owns What

| Role | Primary Folder | Can also edit |
|---|---|---|
| ☁️ Cloud Architect | `infrastructure/`, `docs/`, `.github/` | Reviews everything |
| ⚙️ Data Engineer | `pipeline/` | `config/`, `schemas/` |
| 📊 Data Analyst | `sql/`, `notebooks/` | `docs/` |
| 🖥️ Simulation Engineer | `data_generator/` | `schemas/` |

**If you need to change someone else's folder:** open a PR and assign them as reviewer. Don't commit directly.

---

## 🚫 Never Commit These

| What | Why | How to fix |
|---|---|---|
| `.env` | Contains real project IDs and secrets | Add to `.gitignore`. Use `.env.example` instead. |
| `*.json` key files | GCP service account credentials = full account access | They're blocked by `.gitignore`. Never override. |
| `venv/` or `.venv/` | 100MB+ of packages, different on every machine | Blocked by `.gitignore`. Use `requirements.txt`. |
| Notebook outputs | Giant binary blobs, cause unreadable diffs | Clear outputs before committing: `Kernel → Restart & Clear Output` |
| Passwords/tokens in code | If pushed, must be rotated immediately | Use `.env` + `python-dotenv` |

### Quick safety check before every `git push`

```bash
# Run this — should print nothing dangerous
git diff --staged | grep -iE "(password|secret|private_key|token|api_key)" | grep "^+"
```

---

## ✅ How to Avoid Merge Conflicts

### Rule 1 — Always pull before you branch

```bash
git checkout develop
git pull origin develop        # Get latest from all teammates
git checkout -b feature/my-task
```

### Rule 2 — Keep branches short-lived

Merge within **2–3 days**. Branches left open for a week always cause conflicts.

### Rule 3 — Sync your branch if develop moved

```bash
# While on your feature branch:
git fetch origin
git merge origin/develop       # Bring in your teammates' latest work
# Resolve any conflicts, then continue
```

### Rule 4 — One person per file at a time

Communicate before editing a shared file. A quick "I'm editing `silver.sql`" in the team chat prevents most conflicts.

### Rule 5 — `requirements.txt` is high-conflict

If you add a dependency:
1. Add it to `requirements.txt` in its own commit
2. Immediately push and announce to the team: "I added `pydantic==2.6.4` to requirements — run `pip install -r requirements.txt`"

---

## 🔍 Code Review Guidelines

### For the reviewer

A good review takes 10–15 minutes. Check these 4 things:

1. **Safety** — No credentials, no `.env`, no hardcoded secrets
2. **Correctness** — Does the logic make sense? Any edge cases missed?
3. **Readability** — Variable names clear? Functions do one thing?
4. **Impact** — Does this break anything for another team member?

**How to write a good comment:**

```
# Too vague — not helpful:
"This is wrong."

# Better — specific and constructive:
"This will fail if `speed_kmh` is None (the simulator can produce null
values for stationary vehicles). Add a null check:
  if event.get('speed_kmh') is None: return
```

### For the PR author

- Keep PRs **small** — one feature, one PR. Big PRs don't get reviewed well.
- Don't merge your own PR. Ask a teammate.
- Respond to review comments within 24 hours.
- If you disagree with a comment, explain why — it's a discussion, not a verdict.

---

## 💬 Communication Norms

| Situation | Action |
|---|---|
| About to edit a file someone else might be working on | Send a message in team chat first |
| PR open for more than 24h with no review | Ping the reviewer directly |
| Merging `develop` → `main` | Announce to the full team first |
| Found a bug in someone else's code | Open a `fix/` branch or raise a GitHub Issue |
| Schema change that affects multiple components | Discuss with all relevant owners before opening a PR |

---

## 🛠️ Local Development Workflow

```
Before you start: git pull origin develop
While working:    git add <files> → git commit → git push
When done:        Open PR → request review → respond to comments → merge
After merging:    git checkout develop → git pull → delete old branch
```

That's it. Don't overthink it.
