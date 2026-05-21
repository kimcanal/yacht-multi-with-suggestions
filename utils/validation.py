import hmac
import secrets
from config import USERNAME_RE


def normalize_username(raw):
    username = (raw or "").strip()
    if not USERNAME_RE.fullmatch(username):
        return None
    return username


def safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        try:
            iv = int(v)
        except (TypeError, ValueError):
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
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None
        if iv not in (0, 1):
            return None
        out.append(iv)
    return out



def normalize_scorecard(scorecard):
    if not isinstance(scorecard, list) or len(scorecard) != 12:
        return None
    out = []
    for v in scorecard:
        if v is None:
            out.append(None)
            continue
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None
        if iv < 0:
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
