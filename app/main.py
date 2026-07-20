from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    RESULT_CHOICES,
    STATUS_CHOICES,
    XI_SIZE,
    Availability,
    Game,
    Lineup,
    Team,
    User,
)

main_bp = Blueprint("main", __name__)


def organizer_required():
    if not current_user.is_organizer:
        abort(403)


@main_bp.route("/")
def index():
    # Public marketing landing page for logged-out visitors.
    if not current_user.is_authenticated:
        stats = {
            "teams": Team.query.count(),
            "players": User.query.filter_by(role="player").count(),
            "fixtures": Game.query.filter(
                Game.starts_at >= datetime.now()
            ).count(),
        }
        return render_template("landing.html", stats=stats)

    teams = Team.query.order_by(Team.division, Team.name).all()

    if current_user.is_organizer:
        dashboard = _dashboard_stats(teams)
        return render_template(
            "index.html", teams=teams, dashboard=dashboard, my_upcoming=[]
        )

    my_upcoming = []
    if current_user.team_id:
        my_upcoming = (
            Game.query.filter(
                Game.team_id == current_user.team_id,
                Game.starts_at >= datetime.now(),
            )
            .order_by(Game.starts_at)
            .limit(5)
            .all()
        )
    my_status = _status_map(current_user, my_upcoming)
    in_counts = _in_counts(my_upcoming)
    return render_template(
        "index.html",
        teams=teams,
        my_upcoming=my_upcoming,
        my_status=my_status,
        in_counts=in_counts,
        dashboard=None,
    )


@main_bp.route("/team/<int:team_id>")
@login_required
def team_detail(team_id):
    team = db.get_or_404(Team, team_id)
    roster = (
        User.query.filter_by(team_id=team.id, role="player")
        .order_by(User.name)
        .all()
    )
    upcoming = (
        Game.query.filter(
            Game.team_id == team.id, Game.starts_at >= datetime.now()
        )
        .order_by(Game.starts_at)
        .all()
    )
    past = (
        Game.query.filter(
            Game.team_id == team.id, Game.starts_at < datetime.now()
        )
        .order_by(Game.starts_at.desc())
        .all()
    )
    my_status = _status_map(current_user, upcoming)
    in_counts = _in_counts(upcoming)

    # Availability heatmap: {(user_id, game_id): status} over upcoming fixtures.
    matrix = {}
    if upcoming:
        game_ids = [g.id for g in upcoming]
        for a in Availability.query.filter(
            Availability.game_id.in_(game_ids)
        ).all():
            matrix[(a.user_id, a.game_id)] = a.status

    # Last 5 results, oldest -> newest for left-to-right form display.
    form = list(reversed([g for g in past if g.result][:5]))

    return render_template(
        "team.html",
        team=team,
        roster=roster,
        upcoming=upcoming,
        past=past,
        my_status=my_status,
        in_counts=in_counts,
        matrix=matrix,
        form=form,
    )


@main_bp.route("/team/<int:team_id>/games/new", methods=["GET", "POST"])
@login_required
def new_game(team_id):
    organizer_required()
    team = db.get_or_404(Team, team_id)

    if request.method == "POST":
        opponent = request.form.get("opponent", "").strip()
        date_str = request.form.get("date", "")
        time_str = request.form.get("time", "")
        venue = request.form.get("venue", "").strip()
        is_home = request.form.get("is_home") == "home"
        notes = request.form.get("notes", "").strip()

        errors = []
        if not opponent:
            errors.append("Opponent is required.")
        starts_at = None
        try:
            starts_at = datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            errors.append("A valid date and time are required.")
        overs = _parse_int(request.form.get("overs"), "Overs per side", errors, lo=1, hi=100)

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "game_form.html", team=team, form=request.form
            )

        game = Game(
            team_id=team.id,
            opponent=opponent,
            starts_at=starts_at,
            venue=venue or None,
            is_home=is_home,
            notes=notes or None,
            overs=overs,
        )
        db.session.add(game)
        db.session.commit()
        flash("Fixture added.", "success")
        return redirect(url_for("main.team_detail", team_id=team.id))

    return render_template("game_form.html", team=team, form={})


@main_bp.route("/game/<int:game_id>")
@login_required
def game_detail(game_id):
    game = db.get_or_404(Game, game_id)
    roster = (
        User.query.filter_by(team_id=game.team_id, role="player")
        .order_by(User.name)
        .all()
    )
    # Map user_id -> status for this game.
    responses = {a.user_id: a.status for a in game.availabilities}

    board = {"available": [], "maybe": [], "unavailable": [], "no_response": []}
    for player in roster:
        status = responses.get(player.id)
        board[status if status else "no_response"].append(player)

    my_status = responses.get(current_user.id)
    can_respond = current_user.team_id == game.team_id
    lineup_count = Lineup.query.filter_by(game_id=game.id).count()
    return render_template(
        "game.html",
        game=game,
        board=board,
        roster=roster,
        my_status=my_status,
        can_respond=can_respond,
        result_choices=RESULT_CHOICES,
        lineup_count=lineup_count,
        xi_size=XI_SIZE,
    )


def _parse_int(raw, field, errors, lo=None, hi=None):
    """Parse an optional integer form field, appending a message on error."""
    raw = (raw or "").strip()
    if raw == "":
        return None
    try:
        v = int(raw)
    except ValueError:
        errors.append(f"{field} must be a whole number.")
        return None
    if lo is not None and v < lo:
        errors.append(f"{field} can't be less than {lo}.")
        return None
    if hi is not None and v > hi:
        errors.append(f"{field} can't be more than {hi}.")
        return None
    return v


def _parse_overs(raw, field, errors, max_overs=None):
    """Parse cricket overs like "39.4" (39 overs, 4 balls). Balls are 0–5."""
    raw = (raw or "").strip()
    if raw == "":
        return None
    try:
        v = float(raw)
    except ValueError:
        errors.append(f"{field} must be a number like 39.4.")
        return None
    if v < 0:
        errors.append(f"{field} can't be negative.")
        return None
    whole = int(v)
    balls = round((v - whole) * 10)
    if balls > 5:
        errors.append(f"{field}: balls after the dot must be 0–5.")
        return None
    if max_overs is not None and (whole > max_overs or (whole == max_overs and balls > 0)):
        errors.append(f"{field} can't exceed the match's {max_overs} overs.")
        return None
    return v


@main_bp.route("/game/<int:game_id>/result", methods=["POST"])
@login_required
def record_result(game_id):
    organizer_required()
    game = db.get_or_404(Game, game_id)

    result = request.form.get("result") or None
    if result and result not in RESULT_CHOICES:
        abort(400)

    batted = request.form.get("batted_first")  # "us" / "them" / ""
    we_batted_first = True if batted == "us" else False if batted == "them" else None

    errors = []
    overs = _parse_int(request.form.get("overs"), "Match overs", errors, lo=1, hi=100)
    our_runs = _parse_int(request.form.get("our_runs"), "Your runs", errors, lo=0)
    our_wkts = _parse_int(request.form.get("our_wkts"), "Your wickets", errors, lo=0, hi=10)
    our_overs = _parse_overs(request.form.get("our_overs"), "Your overs", errors, max_overs=overs)
    opp_runs = _parse_int(request.form.get("opp_runs"), "Opponent runs", errors, lo=0)
    opp_wkts = _parse_int(request.form.get("opp_wkts"), "Opponent wickets", errors, lo=0, hi=10)
    opp_overs = _parse_overs(request.form.get("opp_overs"), "Opponent overs", errors, max_overs=overs)

    # Consistency: an explicit decisive result must agree with the totals.
    if result in ("won", "lost", "tie") and our_runs is not None and opp_runs is not None:
        if result == "won" and our_runs <= opp_runs:
            errors.append("Result is 'Won' but your total isn't higher — check the scores.")
        if result == "lost" and our_runs >= opp_runs:
            errors.append("Result is 'Lost' but your total isn't lower — check the scores.")
        if result == "tie" and our_runs != opp_runs:
            errors.append("Result is 'Tied' but the totals aren't equal.")

    # A chasing side can't be all out and still win by wickets.
    if result == "won" and we_batted_first is False and our_wkts == 10:
        errors.append("You can't win by wickets if you were all out — check who batted first.")
    if result == "lost" and we_batted_first is True and opp_wkts == 10:
        errors.append("They can't win by wickets while all out — check who batted first.")

    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("main.game_detail", game_id=game.id))

    # If no result was chosen but both totals are in, derive it from the runs.
    if not result and our_runs is not None and opp_runs is not None:
        result = "won" if our_runs > opp_runs else "lost" if our_runs < opp_runs else "tie"

    game.overs = overs
    game.result = result
    game.we_batted_first = we_batted_first
    game.our_runs, game.our_wkts, game.our_overs = our_runs, our_wkts, our_overs
    game.opp_runs, game.opp_wkts, game.opp_overs = opp_runs, opp_wkts, opp_overs
    game.motm = (request.form.get("motm") or "").strip() or None
    db.session.commit()
    flash("Result saved." if result else "Scorecard cleared.", "success")
    return redirect(url_for("main.game_detail", game_id=game.id))


@main_bp.route("/game/<int:game_id>/selection", methods=["GET"])
@login_required
def selection(game_id):
    """Captain's matrix — pick the XI from the available squad."""
    organizer_required()
    game = db.get_or_404(Game, game_id)
    roster = (
        User.query.filter_by(team_id=game.team_id, role="player")
        .order_by(User.name)
        .all()
    )
    responses = {a.user_id: a.status for a in game.availabilities}
    picked = {l.user_id for l in game.lineup}

    # Sort: available first, then maybe, then no-response, then unavailable.
    order = {"available": 0, "maybe": 1, None: 2, "unavailable": 3}
    rows = sorted(
        roster, key=lambda p: (order.get(responses.get(p.id), 2), p.name)
    )
    return render_template(
        "selection.html",
        game=game,
        rows=rows,
        responses=responses,
        picked=picked,
        xi_size=XI_SIZE,
    )


@main_bp.route("/game/<int:game_id>/pick", methods=["POST"])
@login_required
def pick(game_id):
    """Toggle a player in/out of the XI (AJAX from the captain's matrix)."""
    organizer_required()
    game = db.get_or_404(Game, game_id)
    user_id = request.form.get("user_id", type=int)
    player = db.session.get(User, user_id) if user_id else None
    if player is None or player.team_id != game.team_id:
        abort(400)

    entry = Lineup.query.filter_by(game_id=game.id, user_id=user_id).first()
    selected = False
    if entry:
        db.session.delete(entry)
    else:
        db.session.add(Lineup(game_id=game.id, user_id=user_id))
        selected = True
    db.session.commit()

    count = Lineup.query.filter_by(game_id=game.id).count()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"selected": selected, "count": count, "full": count >= XI_SIZE})
    return redirect(url_for("main.selection", game_id=game.id))


@main_bp.route("/game/<int:game_id>/respond", methods=["POST"])
@login_required
def respond(game_id):
    game = db.get_or_404(Game, game_id)
    if current_user.team_id != game.team_id:
        abort(403)

    status = request.form.get("status")
    if status not in STATUS_CHOICES:
        abort(400)

    entry = Availability.query.filter_by(
        user_id=current_user.id, game_id=game.id
    ).first()
    if entry is None:
        entry = Availability(user_id=current_user.id, game_id=game.id)
        db.session.add(entry)
    entry.status = status
    db.session.commit()

    # AJAX callers get JSON back so the UI can update in place.
    if request.headers.get("X-Requested-With") == "fetch":
        in_count = _in_counts([game]).get(game.id, 0)
        return jsonify(
            {"status": status, "in_count": in_count, "short": in_count < SQUAD_TARGET}
        )

    flash("Availability updated.", "success")
    return redirect(request.form.get("next") or url_for("main.game_detail", game_id=game.id))


# --------------------------------------------------------------------------
# Team, roster, player and profile management
# --------------------------------------------------------------------------

def _email_taken(email, exclude_id=None):
    q = User.query.filter(db.func.lower(User.email) == email.lower())
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    return db.session.query(q.exists()).scalar()


@main_bp.route("/team/<int:team_id>/edit", methods=["GET", "POST"])
@login_required
def edit_team(team_id):
    organizer_required()
    team = db.get_or_404(Team, team_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        division = request.form.get("division", "").strip()
        errors = []
        if not name:
            errors.append("Team name is required.")
        if not division:
            errors.append("Division is required.")
        clash = Team.query.filter(
            db.func.lower(Team.name) == name.lower(), Team.id != team.id
        ).first()
        if name and clash:
            errors.append("Another team already has that name.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("team_edit.html", team=team, form=request.form)
        team.name = name
        team.division = division
        db.session.commit()
        flash("Team details updated.", "success")
        return redirect(url_for("main.team_detail", team_id=team.id))
    return render_template(
        "team_edit.html",
        team=team,
        form={"name": team.name, "division": team.division},
    )


@main_bp.route("/team/<int:team_id>/roster")
@login_required
def edit_roster(team_id):
    organizer_required()
    team = db.get_or_404(Team, team_id)
    roster = (
        User.query.filter_by(team_id=team.id, role="player")
        .order_by(User.name)
        .all()
    )
    # Players who could be added: unassigned first, then those on other teams.
    addable = (
        User.query.filter(
            User.role == "player",
            db.or_(User.team_id.is_(None), User.team_id != team.id),
        )
        .order_by(User.team_id.is_(None).desc(), User.name)
        .all()
    )
    return render_template(
        "roster.html", team=team, roster=roster, addable=addable
    )


@main_bp.route("/team/<int:team_id>/roster/add", methods=["POST"])
@login_required
def roster_add(team_id):
    organizer_required()
    team = db.get_or_404(Team, team_id)

    # Moving an existing player onto this team.
    user_id = request.form.get("user_id", type=int)
    if user_id:
        player = db.session.get(User, user_id)
        if player and player.role == "player":
            player.team_id = team.id
            db.session.commit()
            flash(f"{player.name} added to {team.name}.", "success")
        return redirect(url_for("main.edit_roster", team_id=team.id))

    # Otherwise create a brand-new player on this team.
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    errors = []
    if not name:
        errors.append("New player needs a name.")
    if not email:
        errors.append("New player needs an email.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if email and _email_taken(email):
        errors.append("That email is already registered.")
    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("main.edit_roster", team_id=team.id))
    player = User(name=name, email=email, role="player", team_id=team.id)
    player.set_password(password)
    db.session.add(player)
    db.session.commit()
    flash(f"{name} created and added to {team.name}.", "success")
    return redirect(url_for("main.edit_roster", team_id=team.id))


@main_bp.route("/team/<int:team_id>/roster/remove", methods=["POST"])
@login_required
def roster_remove(team_id):
    organizer_required()
    team = db.get_or_404(Team, team_id)
    user_id = request.form.get("user_id", type=int)
    player = db.session.get(User, user_id) if user_id else None
    if player and player.team_id == team.id:
        player.team_id = None
        db.session.commit()
        flash(f"{player.name} removed from {team.name}.", "info")
    return redirect(url_for("main.edit_roster", team_id=team.id))


@main_bp.route("/players")
@login_required
def players():
    organizer_required()
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like))
        )
    people = query.order_by(User.role.desc(), User.name).all()
    return render_template("players.html", people=people, q=q)


@main_bp.route("/player/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_player(user_id):
    organizer_required()
    user = db.get_or_404(User, user_id)
    teams = Team.query.order_by(Team.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", user.role)
        team_id = request.form.get("team_id") or None
        password = request.form.get("password", "")
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if email and _email_taken(email, exclude_id=user.id):
            errors.append("That email is already in use.")
        if role not in ("player", "organizer"):
            errors.append("Invalid role.")
        if role == "player" and not team_id:
            errors.append("Players must belong to a team.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "player_edit.html", user=user, teams=teams, form=request.form
            )
        user.name = name
        user.email = email
        user.role = role
        user.team_id = int(team_id) if role == "player" else None
        if password:
            user.set_password(password)
        db.session.commit()
        flash("Player updated.", "success")
        return redirect(url_for("main.players"))
    form = {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "team_id": str(user.team_id or ""),
    }
    return render_template(
        "player_edit.html", user=user, teams=teams, form=form
    )


@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    teams = Team.query.order_by(Team.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        team_id = request.form.get("team_id") or None
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if email and _email_taken(email, exclude_id=current_user.id):
            errors.append("That email is already in use.")
        if password and len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if current_user.role == "player" and not team_id:
            errors.append("Please choose your team.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("profile.html", teams=teams, form=request.form)
        current_user.name = name
        current_user.email = email
        if current_user.role == "player":
            current_user.team_id = int(team_id)
        if password:
            current_user.set_password(password)
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("main.profile"))
    form = {
        "name": current_user.name,
        "email": current_user.email,
        "team_id": str(current_user.team_id or ""),
    }
    return render_template("profile.html", teams=teams, form=form)


def _status_map(user, games):
    """Return {game_id: status} for the given user across games."""
    if not games:
        return {}
    game_ids = [g.id for g in games]
    rows = Availability.query.filter(
        Availability.user_id == user.id,
        Availability.game_id.in_(game_ids),
    ).all()
    return {r.game_id: r.status for r in rows}


def _in_counts(games):
    """Return {game_id: number_available} for the given games."""
    if not games:
        return {}
    game_ids = [g.id for g in games]
    rows = (
        db.session.query(Availability.game_id, db.func.count())
        .filter(
            Availability.game_id.in_(game_ids),
            Availability.status == "available",
        )
        .group_by(Availability.game_id)
        .all()
    )
    counts = {gid: n for gid, n in rows}
    return {g.id: counts.get(g.id, 0) for g in games}


# A team is "short" when fewer than this many players are confirmed for its
# next fixture (a cricket XI needs 11).
SQUAD_TARGET = 11


def _dashboard_stats(teams):
    """Aggregate figures for the organizer dashboard (design ref 2a)."""
    now = datetime.now()
    upcoming = (
        Game.query.filter(Game.starts_at >= now).order_by(Game.starts_at).all()
    )
    in_counts = _in_counts(upcoming)

    # Roster size per team (registered players).
    roster_rows = (
        db.session.query(User.team_id, db.func.count())
        .filter(User.role == "player")
        .group_by(User.team_id)
        .all()
    )
    roster_sizes = {tid: n for tid, n in roster_rows}

    # Next fixture per team -> its "in" count.
    next_game = {}
    for g in upcoming:
        if g.team_id not in next_game:
            next_game[g.team_id] = g

    # Completed fixtures (most recent first) for form guides + recent results.
    completed = (
        Game.query.filter(Game.result.isnot(None))
        .order_by(Game.starts_at.desc())
        .all()
    )
    form_by_team = {}
    for g in completed:
        form_by_team.setdefault(g.team_id, []).append(g)

    team_cards = []
    short = 0
    ratios = []
    for team in teams:
        g = next_game.get(team.id)
        in_count = in_counts.get(g.id, 0) if g else None
        is_short = g is not None and in_count < SQUAD_TARGET
        if is_short:
            short += 1
        size = roster_sizes.get(team.id) or 0
        pct = None
        if g is not None and size:
            ratio = min(in_count / size, 1.0)
            ratios.append(ratio)
            pct = round(100 * ratio)
        # Last 5 results, oldest -> newest for left-to-right form display.
        form = list(reversed(form_by_team.get(team.id, [])[:5]))
        team_cards.append(
            {
                "team": team,
                "next": g,
                "in_count": in_count,
                "short": is_short,
                "size": size,
                "pct": pct,
                "form": form,
            }
        )

    avg_pct = round(100 * sum(ratios) / len(ratios)) if ratios else 0
    # Fixtures in the next 7 days, for the dashboard schedule strip.
    week_ahead = now + timedelta(days=7)
    next_week = [g for g in upcoming if g.starts_at <= week_ahead]
    next_week_counts = _in_counts(next_week)
    return {
        "upcoming_count": len(upcoming),
        "short_count": short,
        "avg_pct": avg_pct,
        "team_cards": team_cards,
        "next_week": next_week,
        "next_week_counts": next_week_counts,
        "recent_results": completed[:6],
    }
