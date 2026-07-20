# Cricket Club Scheduler

A Flask web app for managing schedules and player availability across the
club's **12 teams**, each in its own league division.

## Features

- **Accounts & login** — players and organizers register with email/password.
- **Teams, divisions & rosters** — 12 teams are seeded automatically, each in a
  different division. A player belongs to one team; the roster is everyone
  registered to that team.
- **Schedules / fixtures** — organizers add fixtures per team (opponent, date,
  time, venue, home/away, notes).
- **Availability collection** — players mark **Available / Maybe / Out** for
  each of their team's upcoming games in one click.
- **Availability dashboard** — every fixture has a board showing who is
  available, maybe, out, or hasn't responded, with headcounts to help pick the
  lineup.

## Roles

- **Player** — chooses a team at registration, sees their team's fixtures and
  sets their own availability.
- **Organizer** — no team; can add fixtures to any team and view every
  availability board. (Organizer-only actions are guarded — players get a 403.)

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

Then open http://127.0.0.1:5000 and register an account.

The database (`instance/cricket.db`, SQLite) and the 12 teams are created
automatically on first run.

### Configuration

Set via environment variables (all optional):

- `SECRET_KEY` — session signing key (set a real value in production).
- `DATABASE_URL` — SQLAlchemy URL (defaults to local SQLite).

## Project layout

```
run.py               entry point
app/
  __init__.py        app factory, DB init, error handlers
  extensions.py      db + login manager
  models.py          Team, User, Game, Availability
  seed.py            the 12 default teams
  auth.py            register / login / logout
  main.py            teams, fixtures, availability, dashboard
  templates/         Jinja2 templates
  static/style.css   styling
```

## Notes / possible next steps

- A player currently belongs to a single team. Multi-team players (e.g. someone
  in both a Saturday and Sunday XI) would need a roster join table.
- Fixtures are entered manually; a bulk import or league-fixture sync could be
  added.
- Editing/deleting fixtures and email reminders are not yet implemented.
