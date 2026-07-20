# 🏏 Westbridge CC — Cricket Club Scheduler

A Flask + SQLite web app for managing schedules and player availability across a
club's **12 teams**, each playing in its own league division.

Built as a working prototype: everything runs locally from a single SQLite file,
no external services required.

---

## Features

**Accounts & roles**
- Email/password login with two roles: **Player** and **Organizer** (admin).
- Players see their own team; organizers manage everything.
- Everyone can edit their own profile (name, email, password, team).
- Organizer-only actions are guarded — players get a clean `403`.

**Teams, divisions & rosters**
- 12 teams seeded automatically, each in a different division.
- Organizers can edit team details, and add/remove/create/move players via a
  roster manager. A searchable **Players** admin lists everyone.

**Fixtures**
- Organizers add fixtures per team: opponent, date/time, venue, home/away,
  notes, and match format (**overs per side**).
- Every fixture carries a **status badge** — Upcoming / Today / Result pending /
  Won / Lost / Draw / No result.

**Availability**
- Players mark **I'm in / Maybe / Can't make it** in one tap (AJAX, no reload).
- Live "N in" counts, amber when a team is short of 11.
- Per-fixture availability board and a team **availability heatmap**
  (players × fixtures).

**Captain's tools**
- **XI selection matrix** — pick the eleven from the available squad with a live
  counter that turns green at a full side.

**Results & scorecards**
- Structured, **validated numeric scorecards** (runs / wickets / overs).
- Margins are **computed** and always consistent — a chasing win shows
  "by N wickets", a defended win shows "by N runs".
- Handles **DNB / abandoned (No result)** matches.

**Dashboards & polish**
- Organizer dashboard: stat tiles, availability donut + per-team bars,
  "Next 7 days" strip, last-5 **form guides**, and recent results.
- **Dark mode** toggle, responsive layout, "Cobalt" visual system
  (Space Grotesk + IBM Plex Sans).

---

## Quick start (local)

Requires **Python 3.10+**.

```bash
# 1. Install dependencies in a virtualenv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. (Optional) load demo data — 12 teams, players, fixtures, results
.venv/bin/python sample_data.py

# 3. Run the development server
.venv/bin/python run.py
```

Open **http://127.0.0.1:5000**.

If you skip step 2, the database and the 12 teams are still created on first
run — you just start with no players or fixtures. Register an organizer account
to begin, or use the demo logins below.

### Demo logins

After running `sample_data.py` (all passwords: `password`):

| Role  | Email               |
|-------|---------------------|
| Admin | `ammar@cricket.net` |
| Player| `imran@cricket.net` |

Any other seeded player is `first.last@club.net`, password `password`.

### Reseeding

```bash
.venv/bin/python sample_data.py           # seeds only if empty
.venv/bin/python sample_data.py --reset   # wipes users/games/availability, reseeds
```

---

## Configuration

Set via environment variables (all optional for local use):

| Variable       | Default                | Purpose                              |
|----------------|------------------------|--------------------------------------|
| `SECRET_KEY`   | `dev-secret-change-me` | Session signing key — **set a real value in production**. |
| `DATABASE_URL` | `sqlite:///cricket.db` | SQLAlchemy database URL.             |

The SQLite file lives at `instance/cricket.db` and is created automatically.

> **Production:** do not run `run.py` as-is on a public network — it uses the
> Flask dev server with `debug=True`. See **[DEPLOY.md](DEPLOY.md)**.

---

## Project layout

```
run.py               dev entry point (Flask dev server)
requirements.txt     dependencies
sample_data.py       demo data seeder (teams, players, fixtures, results)
DEPLOY.md            production deployment guide
app/
  __init__.py        app factory, DB init, error handlers
  extensions.py      db + login manager
  models.py          Team, User, Game, Availability, Lineup
  seed.py            the 12 default teams
  auth.py            register / login / logout
  main.py            teams, fixtures, availability, results, dashboard
  templates/         Jinja2 templates
  static/
    style.css        Cobalt design system (light + dark)
    app.js           availability AJAX, tabs, theme toggle, animations
```

## Data model

- **Team** — name, division; has many players and games.
- **User** — name, email, password hash, role (player/organizer), team.
- **Game** — opponent, start time, venue, home/away, overs, and a recorded
  result (runs/wickets/overs per side, who batted first, MOTM).
- **Availability** — a user's status (available/maybe/unavailable) for a game.
- **Lineup** — a player selected in the XI for a game (captain's pick).

## Possible next steps

- Per-user login tracking (`last_login_at`) for a real "recent activity" view.
- Multi-team players (a roster join table).
- Editing/deleting fixtures; bulk fixture import.
- Email/notification reminders.
