from app.extensions import db
from app.models import Team

# The 12 club teams, each in its own division.
DEFAULT_TEAMS = [
    ("1st XI", "Premier Division"),
    ("2nd XI", "Division One"),
    ("3rd XI", "Division Two"),
    ("4th XI", "Division Three"),
    ("Sunday XI", "Sunday League"),
    ("T20 Warriors", "T20 Cup"),
    ("Colts U19", "Youth Division A"),
    ("Colts U15", "Youth Division B"),
    ("Colts U13", "Youth Division C"),
    ("Womens 1st XI", "Womens Premier"),
    ("Womens 2nd XI", "Womens Division One"),
    ("Development XI", "Development League"),
]


def seed_teams():
    """Create the 12 default teams once, if the table is empty."""
    if Team.query.count() > 0:
        return
    for name, division in DEFAULT_TEAMS:
        db.session.add(Team(name=name, division=division))
    db.session.commit()
