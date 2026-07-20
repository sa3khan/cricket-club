from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    division = db.Column(db.String(120), nullable=False)

    players = db.relationship("User", back_populates="team")
    games = db.relationship(
        "Game", back_populates="team", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Team {self.name} ({self.division})>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # "player" or "organizer"
    role = db.Column(db.String(20), nullable=False, default="player")
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)

    team = db.relationship("Team", back_populates="players")
    availabilities = db.relationship(
        "Availability", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_organizer(self):
        return self.role == "organizer"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    opponent = db.Column(db.String(120), nullable=False)
    # stored as a real datetime so we can sort and compare
    starts_at = db.Column(db.DateTime, nullable=False)
    venue = db.Column(db.String(200), nullable=True)
    is_home = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.String(300), nullable=True)

    # Match format: overs allowed per side (e.g. 20, 40, 50).
    overs = db.Column(db.Integer, nullable=True)

    # Result of a completed fixture (None until recorded).
    # result: "won", "lost", "draw", "tie", "no_result"
    result = db.Column(db.String(20), nullable=True)
    our_runs = db.Column(db.Integer, nullable=True)
    our_wkts = db.Column(db.Integer, nullable=True)
    our_overs = db.Column(db.Float, nullable=True)
    opp_runs = db.Column(db.Integer, nullable=True)
    opp_wkts = db.Column(db.Integer, nullable=True)
    opp_overs = db.Column(db.Float, nullable=True)
    # True = our team batted first, False = we chased, None = unknown.
    we_batted_first = db.Column(db.Boolean, nullable=True)
    motm = db.Column(db.String(120), nullable=True)

    team = db.relationship("Team", back_populates="games")
    availabilities = db.relationship(
        "Availability", back_populates="game", cascade="all, delete-orphan"
    )
    lineup = db.relationship(
        "Lineup", back_populates="game", cascade="all, delete-orphan"
    )

    @property
    def is_past(self):
        return self.starts_at < datetime.now()

    @property
    def has_result(self):
        return self.result is not None

    @staticmethod
    def _fmt_overs(ov):
        """0.0 -> "0", 40.0 -> "40", 39.4 -> "39.4" (the .4 = 4 balls)."""
        if ov is None:
            return None
        whole = int(ov)
        balls = round((ov - whole) * 10)
        return str(whole) if balls == 0 else f"{whole}.{balls}"

    @staticmethod
    def _fmt_innings(runs, wkts, ov):
        if runs is None:
            return None
        if wkts is not None and wkts >= 10:
            s = f"{runs} all out"
        elif wkts is not None:
            s = f"{runs}/{wkts}"
        else:
            s = str(runs)
        ovs = Game._fmt_overs(ov)
        if ovs is not None:
            s += f" ({ovs} ov)"
        return s

    @property
    def our_score(self):
        return self._fmt_innings(self.our_runs, self.our_wkts, self.our_overs)

    @property
    def opp_score(self):
        return self._fmt_innings(self.opp_runs, self.opp_wkts, self.opp_overs)

    @property
    def margin(self):
        """Computed "by N runs/wickets" fragment — never inconsistent.

        The side batting first wins by runs; the side chasing wins by
        wickets in hand. Returns None when it can't be determined.
        """
        if self.result not in ("won", "lost"):
            return None
        if self.our_runs is None or self.opp_runs is None:
            return None
        if self.we_batted_first is None:
            return None
        won = self.result == "won"
        # Whoever won — did they bat first (win by runs) or chase (by wickets)?
        winner_batted_first = self.we_batted_first if won else (not self.we_batted_first)
        if winner_batted_first:
            return f"by {abs(self.our_runs - self.opp_runs)} runs"
        # Chased it down: wickets in hand belong to the winner.
        winner_wkts = self.our_wkts if won else self.opp_wkts
        if winner_wkts is None:
            return None
        return f"by {10 - winner_wkts} wickets"

    @property
    def result_summary(self):
        """Full human sentence for the scorecard footer."""
        if not self.result:
            return None
        if self.result == "tie":
            return "Match tied"
        if self.result == "no_result":
            return "No result — match abandoned"
        who = self.team.name if self.result == "won" else self.opponent
        m = self.margin
        return f"{who} won {m}" if m else f"{who} won"

    @property
    def schedule_state(self):
        """Coarse scheduling state used for status badges."""
        now = datetime.now()
        if self.result:
            return self.result  # won / lost / draw / tie / no_result
        if self.starts_at < now:
            return "completed"  # played, result not yet recorded
        if self.starts_at.date() == now.date():
            return "today"
        return "upcoming"

    def __repr__(self):
        return f"<Game {self.team_id} vs {self.opponent} @ {self.starts_at}>"


class Availability(db.Model):
    __tablename__ = "availabilities"
    __table_args__ = (
        db.UniqueConstraint("user_id", "game_id", name="uq_user_game"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    # "available", "unavailable", or "maybe"
    status = db.Column(db.String(20), nullable=False, default="maybe")
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now
    )

    user = db.relationship("User", back_populates="availabilities")
    game = db.relationship("Game", back_populates="availabilities")


class Lineup(db.Model):
    """A player picked in the XI for a fixture (captain's selection)."""

    __tablename__ = "lineups"
    __table_args__ = (
        db.UniqueConstraint("user_id", "game_id", name="uq_lineup_user_game"),
    )

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Optional role: "captain", "keeper", or None.
    role = db.Column(db.String(20), nullable=True)

    game = db.relationship("Game", back_populates="lineup")
    user = db.relationship("User")


STATUS_CHOICES = ("available", "maybe", "unavailable")

# Human-readable labels + badge kind for each scheduling / result state.
STATE_META = {
    "upcoming": ("Upcoming", "upcoming"),
    "today": ("Today", "today"),
    "completed": ("Completed", "neutral"),
    "won": ("Won", "won"),
    "lost": ("Lost", "lost"),
    "draw": ("Draw", "draw"),
    "tie": ("Tied", "draw"),
    "no_result": ("No result", "neutral"),
}
RESULT_CHOICES = ("won", "lost", "draw", "tie", "no_result")
XI_SIZE = 11
