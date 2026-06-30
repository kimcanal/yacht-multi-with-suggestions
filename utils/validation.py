import hmac
import secrets
from config import USERNAME_RE


_SCORECARD_SCORE_BOUNDS = (
    (0, 5),
    (0, 10),
    (0, 15),
    (0, 20),
    (0, 25),
    (0, 30),
    (0, 30),
    (0, 30),
    (0, 30),
    (0, 15),
    (0, 30),
    (0, 1150),
)


def normalize_username(raw):
    username = (raw or "").strip()
    if not USERNAME_RE.fullmatch(username):
        return None
    return username


def _coerce_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_int(value, default=None):
    parsed = _coerce_int(value)
    if parsed is None:
        return default
    return parsed


def issue_player_token():
    return secrets.token_urlsafe(24)


def is_valid_player(room, username, player_token):
    if not username or not player_token:
        return False
    expected = room.get("player_tokens", {}).get(username)
    return bool(expected) and hmac.compare_digest(expected, player_token)


def normalize_dice(dice):
    if not isinstance(dice, list) or len(dice) != 5:
        return None
    out = []
    for v in dice:
        iv = _coerce_int(v)
        if iv is None:
            return None
        if iv < 1 or iv > 6:
            return None
        out.append(iv)
    return out


def normalize_kept(kept):
    if not isinstance(kept, list) or len(kept) != 5:
        return None
    out = []
    for v in kept:
        iv = _coerce_int(v)
        if iv is None:
            return None
        if iv not in (0, 1):
            return None
        out.append(iv)
    return out



def normalize_scorecard(scorecard):
    if not isinstance(scorecard, list) or len(scorecard) != 12:
        return None
    out = []
    for idx, v in enumerate(scorecard):
        if v is None:
            out.append(None)
            continue
        iv = _coerce_int(v)
        if iv is None:
            return None
        min_score, max_score = _SCORECARD_SCORE_BOUNDS[idx]
        if iv < min_score or iv > max_score:
            return None
        if idx == 9 and iv not in (0, 15):
            return None
        if idx == 10 and iv not in (0, 30):
            return None
        if idx == 11 and iv not in (0, 50) and (iv < 150 or (iv - 50) % 100 != 0):
            return None
        out.append(iv)
    return out


def normalize_strategy_mode(value):
    mode = (value or "focused")
    if mode not in ("focused", "cover"):
        return None
    return mode


def normalize_rolls_left(value, min_value=0, max_value=3):
    parsed = safe_int(value)
    if parsed is None or parsed < min_value or parsed > max_value:
        return None
    return parsed


def normalize_scores_by_players(scores, players):
    if not isinstance(scores, dict):
        return None
    normalized = {}
    for player in players:
        row = normalize_scorecard(scores.get(player))
        if row is None:
            return None
        normalized[player] = row
    extra_keys = [k for k in scores.keys() if k not in players]
    if extra_keys:
        return None
    return normalized
