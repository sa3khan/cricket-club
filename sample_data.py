"""Populate the database with sample organizer, players, fixtures, and
availability responses so the app is immediately explorable.

Run once:  .venv/bin/python sample_data.py

Idempotent-ish: it skips seeding if sample players already exist. Use
`--reset` to wipe users/games/availability first (teams are kept).

Sample logins (all password: "password"):
  organizer:  ammar@cricket.net
  a player:   imran@cricket.net
"""
import random
import sys
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import Availability, Game, Lineup, Team, User

FIRST = [
    "Alex", "Sam", "Jordan", "Chris", "Ravi", "Omar", "Ben", "Tom", "Zain",
    "Liam", "Noah", "Ethan", "Aarav", "Kabir", "Josh", "Dan", "Will", "Harry",
    "Priya", "Aisha", "Maya", "Zara", "Emma", "Grace", "Sophie", "Nina",
]
LAST = [
    "Khan", "Patel", "Smith", "Jones", "Ahmed", "Singh", "Brown", "Taylor",
    "Wilson", "Shah", "Iqbal", "Roberts", "Clarke", "Evans", "Ali", "Hughes",
    "Kaur", "Reddy", "Nair", "Baker", "Ward", "Cole", "Fisher", "Gill",
]
OPPONENTS = [
    "Riverside CC", "Oakwood CC", "St Mary's CC", "Hillcrest CC", "Kingsley CC",
    "Ashford CC", "Bramley CC", "Weston CC", "Fairview CC", "Marlow CC",
    "Denton CC", "Whitfield CC", "Langley CC", "Crossfield CC",
]
VENUES = ["Home Ground", "Memorial Park", "The Oval Rec", "Victoria Field"]
STATUSES = ["available", "available", "available", "maybe", "unavailable"]


def _valid_overs(rng, overs):
    """A realistic overs figure: whole overs + balls (0–5), never .6–.9."""
    whole = rng.randint(int(overs * 0.6), overs - 1)
    return round(whole + rng.randint(0, 5) / 10, 1)


def _record_sample_result(rng, game, players):
    """Attach a plausible numeric scorecard + result to a past fixture."""
    overs = rng.choice([20, 40, 40, 50])

    # ~1 in 8 gets rained off: we bat, opponent doesn't (DNB), no result.
    if rng.random() < 0.12:
        game.overs = overs
        game.result = "no_result"
        game.we_batted_first = True
        game.our_runs = rng.randint(60, 160)
        game.our_wkts = rng.randint(1, 6)
        game.our_overs = _valid_overs(rng, overs)
        if players:
            game.motm = None
        return

    a = rng.randint(120, 240)
    b = rng.randint(120, 240)
    if a == b:
        b -= rng.randint(1, 8)  # avoid accidental ties for cleaner demo
    we_batted_first = rng.choice([True, False])
    game.result = "won" if a > b else "lost"

    # The winner's innings ends when they pass the target if they chased.
    we_won = a > b
    we_chased = not we_batted_first
    a_wkts = rng.randint(2, 9) if (we_won and we_chased) else rng.randint(2, 10)
    b_wkts = rng.randint(2, 9) if ((not we_won) and (not we_chased)) else rng.randint(2, 10)
    a_overs = _valid_overs(rng, overs) if (we_won and we_chased or a_wkts == 10) else float(overs)
    b_overs = _valid_overs(rng, overs) if ((not we_won) and not we_chased or b_wkts == 10) else float(overs)

    game.overs = overs
    game.we_batted_first = we_batted_first
    game.our_runs, game.our_wkts, game.our_overs = a, a_wkts, a_overs
    game.opp_runs, game.opp_wkts, game.opp_overs = b, b_wkts, b_overs
    if players:
        game.motm = rng.choice(players).name


def wipe():
    Lineup.query.delete()
    Availability.query.delete()
    Game.query.delete()
    User.query.delete()
    db.session.commit()


def seed():
    app = create_app()
    with app.app_context():
        if "--reset" in sys.argv:
            wipe()
            print("Wiped users, games, and availability.")

        if User.query.filter_by(role="player").count() > 0:
            print("Players already exist — nothing to do. "
                  "Re-run with --reset to reseed.")
            return

        rng = random.Random(42)

        # One organizer for the whole club.
        organizer = User(name="Ammar Maqsud", email="ammar@cricket.net",
                         role="organizer")
        organizer.set_password("password")
        db.session.add(organizer)

        teams = Team.query.order_by(Team.id).all()
        used_emails = {"ammar@cricket.net", "imran@cricket.net"}
        # The first player seeded gets a memorable demo login.
        demo_player_used = False
        sample_player_email = "imran@cricket.net"
        total_players = 0
        total_games = 0

        for team in teams:
            # 12-14 players per team.
            n = rng.randint(12, 14)
            players = []
            for _ in range(n):
                fn, ln = rng.choice(FIRST), rng.choice(LAST)
                if not demo_player_used:
                    # First player across the whole club gets the demo login.
                    name = "Imran Khan"
                    email = "imran@cricket.net"
                    demo_player_used = True
                else:
                    name = f"{fn} {ln}"
                    base = f"{fn}.{ln}".lower()
                    email = f"{base}@club.test"
                    i = 1
                    while email in used_emails:
                        i += 1
                        email = f"{base}{i}@club.test"
                used_emails.add(email)
                p = User(name=name, email=email, role="player",
                        team_id=team.id)
                p.set_password("password")
                db.session.add(p)
                players.append(p)
            total_players += n

            # 4 upcoming + 2 past fixtures per team.
            db.session.flush()  # assign player ids
            for offset in (-14, -7, 4, 11, 18, 25):
                start = datetime.now().replace(
                    hour=13, minute=0, second=0, microsecond=0
                ) + timedelta(days=offset)
                is_home = rng.random() < 0.5
                game = Game(
                    team_id=team.id,
                    opponent=rng.choice(OPPONENTS),
                    starts_at=start,
                    venue=rng.choice(VENUES) if is_home else None,
                    is_home=is_home,
                    overs=40,
                )
                # Past fixtures get a recorded result + scorecard.
                if offset < 0:
                    _record_sample_result(rng, game, players)
                db.session.add(game)
                db.session.flush()
                total_games += 1

                # Most players respond to upcoming games.
                if offset > 0:
                    responders = []
                    for p in players:
                        if rng.random() < 0.8:  # 20% leave no response
                            st = rng.choice(STATUSES)
                            db.session.add(Availability(
                                user_id=p.id, game_id=game.id, status=st,
                            ))
                            if st == "available":
                                responders.append(p)
                    # Pre-pick an XI for the very next fixture so the
                    # captain's matrix has something to show. Prefer the
                    # available players, then top up from the rest.
                    if offset == 4:
                        picks = responders[:]
                        for p in players:
                            if len(picks) >= 11:
                                break
                            if p not in picks:
                                picks.append(p)
                        for p in picks[:11]:
                            db.session.add(Lineup(
                                user_id=p.id, game_id=game.id,
                            ))

        db.session.commit()
        print(f"Seeded 1 organizer, {total_players} players, "
              f"{total_games} fixtures across {len(teams)} teams.")
        print("\nSample logins (password: 'password'):")
        print(f"  Organizer: ammar@cricket.net")
        print(f"  Player:    {sample_player_email}")


if __name__ == "__main__":
    seed()
