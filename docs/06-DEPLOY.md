# 06 · Deploy

## Local (development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m app.seed --reset                  # optional demo data
python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

Data lives in `.tmp/savings.db` (override with `SAVINGS_DB`).

## Docker (recommended for daily use)

```powershell
docker compose up -d --build      # http://127.0.0.1:8000
```

- The database is kept in the named volume `savings-data` (`/data/savings.db`).
- The port binds to `127.0.0.1` only. To reach it from your phone on the LAN, change the
  mapping to `"8000:8000"` **and** set a password:

  ```powershell
  $env:SAVINGS_PASSWORD = "a-long-random-passphrase"; docker compose up -d
  ```

- Seed demo data inside the container: `docker compose exec savings python -m app.seed --reset`.

## Backup & restore

```powershell
docker compose cp savings:/data/savings.db ./backup-savings.db
docker compose cp ./backup-savings.db savings:/data/savings.db
```

The monthly CSV export (`Export CSV` button) is also a human-readable backup in the
spreadsheet's own layout.

## Exposing it on the internet

Basic auth sends credentials on every request, so only do this behind HTTPS (Caddy, nginx,
Cloudflare Tunnel or Tailscale). Tailscale is the simplest option for a personal finance app:
the container stays private and only your devices can reach it.

## CI

`.github/workflows/ci.yml` runs on every push and PR:

1. Ruff lint and the unit tests on Python 3.10, 3.11 and 3.12.
2. Seeds a demo database.
3. Builds the Docker image and smoke-tests `/api/health` in a running container.

## Environment variables

| Variable           | Default              | Purpose                                   |
|--------------------|----------------------|-------------------------------------------|
| `SAVINGS_DB`       | `.tmp/savings.db`    | SQLite file path                          |
| `SAVINGS_USER`     | `admin`              | Basic auth user                           |
| `SAVINGS_PASSWORD` | *(empty = no auth)*  | Enables Basic auth for everything except `/api/health` |
