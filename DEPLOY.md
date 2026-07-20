# Deployment guide

The dev entry point (`run.py`) runs Flask's **development server with
`debug=True`**. That is fine on your own machine but must **never** be exposed to
an untrusted network — the Werkzeug debugger allows remote code execution on any
traceback. This guide covers running it safely for real.

---

## 1. Prerequisites

- Python 3.10+
- A machine/VM you control (Linux assumed below)

```bash
git clone git@github.com:sa3khan/cricket-club.git
cd cricket-club
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install gunicorn          # production WSGI server
```

## 2. Set environment variables

Never ship the default secret key. Generate one:

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_URL="sqlite:////absolute/path/to/cricket.db"   # or a Postgres URL
```

For Postgres, install the driver and use a URL like
`postgresql+psycopg://user:pass@host/dbname`
(`.venv/bin/pip install "psycopg[binary]"`).

## 3. Initialise the database

Tables are created automatically on first app start. To also load demo data:

```bash
.venv/bin/python sample_data.py           # optional demo teams/players/fixtures
```

> This prototype has **no migration framework**. If `app/models.py` changes,
> the simplest path is a fresh database (`rm instance/cricket.db` then reseed).
> For a real deployment, add Flask-Migrate/Alembic before going live.

## 4. Run under a production server

The app factory is `create_app()` in the `app` package, so gunicorn can import
it directly — `run.py` is **not** used in production:

```bash
.venv/bin/gunicorn "app:create_app()" \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --timeout 60
```

Bind to `127.0.0.1` and put a reverse proxy in front (below) — don't expose
gunicorn directly.

> SQLite + multiple workers: fine for a small club (low write volume), but
> SQLite serialises writes. If you expect real concurrency, move `DATABASE_URL`
> to Postgres.

## 5. Reverse proxy (nginx) + HTTPS

```nginx
server {
    listen 80;
    server_name cricket.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then obtain a certificate (e.g. `certbot --nginx -d cricket.example.com`).

## 6. Run as a service (systemd)

`/etc/systemd/system/cricket.service`:

```ini
[Unit]
Description=Westbridge CC scheduler
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/cricket-club
Environment="SECRET_KEY=change-me-to-a-real-secret"
Environment="DATABASE_URL=sqlite:////opt/cricket-club/instance/cricket.db"
ExecStart=/opt/cricket-club/.venv/bin/gunicorn app:create_app() --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cricket
sudo systemctl status cricket
```

---

## Exposing over Tailscale (private testing)

To share with your own devices only (recommended for testing), use
`tailscale serve` — **not** `tailscale funnel` (which is public internet):

```bash
tailscale serve --bg 8000        # private to your tailnet, HTTPS terminated by Tailscale
# check what's exposed:
tailscale serve status
tailscale funnel status
```

Point it at the **gunicorn** port (8000), not the dev server. If `funnel status`
shows anything, your app is on the public internet — take it down unless that's
intended and you've hardened it (steps 2 & 4 above).

---

## Production checklist

- [ ] `SECRET_KEY` set to a real random value (not the default)
- [ ] Running under **gunicorn**, not `run.py` / `debug=True`
- [ ] Bound to `127.0.0.1`, reachable only via reverse proxy
- [ ] HTTPS enabled
- [ ] `instance/cricket.db` backed up on a schedule (or using Postgres)
- [ ] Not on `tailscale funnel` unless deliberately public
- [ ] (Recommended) add Alembic migrations before the first real users
