# Contributing to YAGL

Thanks for helping make Yet Another Grocery List useful. Please open an issue first for a major feature or schema change. For bug fixes, include steps to reproduce, expected versus actual behavior, YAGL version and relevant sanitized logs.

## Local setup

```bash
python -m pip install -r requirements.txt pytest httpx
YAGL_DB_PATH=/tmp/yagl-local.sqlite3 uvicorn backend.app:app --reload --port 8080
pytest -q
```

PR checklist:
- Keep the core list usable with zero configuration and zero accounts.
- Avoid mandatory external services, tracking, and paid APIs.
- Respect device-specific store selection and shared list semantics.
- Add/update tests and docs when changing behavior, endpoints, or store map formats.
- Avoid breaking existing data or exports; document migration needs.
- Do not submit secrets, location histories, private store profiles, or real shopping lists.
- Ensure any contributions and dependencies are compatible with [LICENSE](LICENSE) (MIT + Commons Clause). Submitting a contribution does not automatically grant copyright ownership to the project maintainer; if a formal contributor agreement is later needed, it will be discussed before requiring it.

Use constructive, respectful discussions. This is a small hobby project with no promised support SLA.
