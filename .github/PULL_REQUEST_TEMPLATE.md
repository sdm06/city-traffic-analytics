## What does this PR do?

<!-- 1-2 sentences. What problem does it solve or what feature does it add? -->



## Type of change

<!-- Put an x inside the brackets that apply: [x] -->

- [ ] `feat` — New feature
- [ ] `fix` — Bug fix
- [ ] `sql` — New or changed SQL
- [ ] `docs` — Documentation only
- [ ] `chore` — Dependencies, configs, tooling
- [ ] `refactor` — Code cleanup, no behaviour change
- [ ] `test` — New or updated tests

## How to test it?

<!-- Step-by-step instructions for the reviewer to verify this works -->

1.
2.
3.

## Related files changed

<!-- List the key files this PR touches -->

- `file/path.py` — reason
- `file/other.sql` — reason

## Checklist

<!-- All boxes must be checked before requesting review -->

- [ ] Code runs locally without errors
- [ ] No credentials, `.env`, or `*.json` key files committed
  ```bash
  # Quick check — should return nothing sensitive:
  git diff origin/develop...HEAD -- . ':(exclude)schemas/' ':(exclude)config/'  | grep -iE "(key|secret|password|token)" | grep "^+" || echo "Clean ✅"
  ```
- [ ] Tests added or updated (if applicable)
- [ ] Notebook outputs cleared (if `.ipynb` files changed)
- [ ] PR targets `develop`, **not** `main`
- [ ] At least one reviewer assigned

## Screenshots / Output (optional)

<!-- Paste terminal output, query results, or dashboard screenshots if helpful -->

```
Paste output here
```
