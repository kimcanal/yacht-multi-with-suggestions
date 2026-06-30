import json
import os
import tempfile
import threading
from datetime import datetime

DATA_FILE = os.getenv('YACHT_DATA_FILE', 'game_data.json')
DATA_LOCK = threading.RLock()
MAX_SCORE = 1000


def _default_data():
    return {'users': {}, 'games': [], 'single_leaderboard': []}


def _now_iso():
    return datetime.now().isoformat()


def _coerce_int(value, default=0, minimum=0, maximum=MAX_SCORE):
    if isinstance(value, bool):
        return default
    if isinstance(value, float) and not value.is_integer():
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _normalize_user(username, raw_user):
    raw_user = raw_user if isinstance(raw_user, dict) else {}
    wins = _coerce_int(raw_user.get('wins', 0))
    draws = _coerce_int(raw_user.get('draws', 0))
    losses = _coerce_int(raw_user.get('losses', 0))
    games_played = _coerce_int(raw_user.get('games_played', wins + draws + losses), maximum=1000000)
    total_score = _coerce_int(raw_user.get('total_score', 0), maximum=MAX_SCORE * max(1, games_played))
    return {
        'username': raw_user.get('username') or username,
        'wins': wins,
        'draws': draws,
        'losses': losses,
        'total_score': total_score,
        'games_played': games_played,
        'created_at': raw_user.get('created_at') or _now_iso(),
    }


def _normalize_game(raw_game):
    if not isinstance(raw_game, dict):
        return None
    player1 = raw_game.get('player1')
    if not player1:
        return None
    player2 = raw_game.get('player2') or None
    score1 = _coerce_int(raw_game.get('score1', 0))
    score2 = _coerce_int(raw_game.get('score2', 0))
    winner = raw_game.get('winner')
    if winner not in {player1, player2, 'DRAW', 'N/A'}:
        if player2 and score1 == score2:
            winner = 'DRAW'
        elif score1 > score2 or not player2:
            winner = player1
        else:
            winner = player2 or 'N/A'
    return {
        'player1': player1,
        'score1': score1,
        'player2': player2,
        'score2': score2,
        'winner': winner,
        'timestamp': raw_game.get('timestamp') or _now_iso(),
    }


def _normalize_single_entry(raw_entry):
    if not isinstance(raw_entry, dict) or not raw_entry.get('username'):
        return None
    return {
        'username': raw_entry.get('username'),
        'score': _coerce_int(raw_entry.get('score', 0)),
        'timestamp': raw_entry.get('timestamp') or _now_iso(),
    }


def _normalize_data(data):
    if not isinstance(data, dict):
        return _default_data()

    users = data.get('users') if isinstance(data.get('users'), dict) else {}
    games = data.get('games') if isinstance(data.get('games'), list) else []
    single_leaderboard = (
        data.get('single_leaderboard')
        if isinstance(data.get('single_leaderboard'), list)
        else []
    )

    normalized = _default_data()
    normalized['users'] = {
        username: _normalize_user(username, row)
        for username, row in users.items()
        if username
    }
    normalized['games'] = [
        game for game in (_normalize_game(row) for row in games) if game is not None
    ]
    normalized['single_leaderboard'] = sorted(
        [
            entry for entry in (_normalize_single_entry(row) for row in single_leaderboard)
            if entry is not None
        ],
        key=lambda row: row['score'],
        reverse=True,
    )[:20]
    return normalized


def _load_data_unlocked():
    if not os.path.exists(DATA_FILE):
        return _default_data()

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _default_data()

    return _normalize_data(data)


def _save_data_unlocked(data):
    directory = os.path.dirname(os.path.abspath(DATA_FILE)) or '.'
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix='.game_data.', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(_normalize_data(data), f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, DATA_FILE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _ensure_user(data, username):
    if username not in data['users']:
        data['users'][username] = {
            'username': username,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'total_score': 0,
            'games_played': 0,
            'created_at': _now_iso()
        }
    else:
        user = data['users'][username]
        user.setdefault('username', username)
        user.setdefault('wins', 0)
        user.setdefault('draws', 0)
        user.setdefault('losses', 0)
        user.setdefault('total_score', 0)
        user.setdefault('games_played', 0)
        user.setdefault('created_at', _now_iso())
    return data['users'][username]


def _clamp_limit(limit, default=10, maximum=50):
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, maximum))


def _sorted_games_desc(games):
    return sorted(games, key=lambda game: game.get('timestamp') or '', reverse=True)


def _serialize_game_entry(game, username=None):
    entry = {
        'player1': game.get('player1'),
        'score1': game.get('score1'),
        'player2': game.get('player2'),
        'score2': game.get('score2'),
        'winner': game.get('winner'),
        'timestamp': game.get('timestamp'),
        'is_multiplayer': bool(game.get('player2')),
    }

    score1 = game.get('score1', 0) or 0
    score2 = game.get('score2', 0) or 0
    entry['margin'] = abs(score1 - score2)

    if not username:
        return entry

    if username == game.get('player1'):
        opponent = game.get('player2')
        score = game.get('score1')
        opponent_score = game.get('score2')
    elif username == game.get('player2'):
        opponent = game.get('player1')
        score = game.get('score2')
        opponent_score = game.get('score1')
    else:
        return None

    winner = game.get('winner')
    if winner == 'DRAW':
        result = 'draw'
    elif winner == username:
        result = 'win'
    else:
        result = 'loss'

    entry.update({
        'username': username,
        'opponent': opponent,
        'score': score,
        'opponent_score': opponent_score,
        'result': result,
    })
    return entry


def _current_streak(recent_games):
    if not recent_games:
        return {'type': None, 'count': 0}

    streak_type = recent_games[0].get('result')
    count = 0
    for game in recent_games:
        if game.get('result') != streak_type:
            break
        count += 1
    return {'type': streak_type, 'count': count}


def load_data():
    """게임 데이터 로드"""
    with DATA_LOCK:
        return _load_data_unlocked()


def save_data(data):
    """게임 데이터 저장"""
    with DATA_LOCK:
        _save_data_unlocked(data)


def get_or_create_user(username):
    """사용자 생성/조회"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        user = _ensure_user(data, username)
        _save_data_unlocked(data)
        return user


def save_game_result(player1_name, player1_score, player2_name, player2_score, result_override=None):
    """게임 결과 저장"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        player1_score = _coerce_int(player1_score)
        player2_score = _coerce_int(player2_score)

        _ensure_user(data, player1_name)
        if player2_name:
            _ensure_user(data, player2_name)

        if result_override == 'player1_win':
            data['users'][player1_name]['wins'] += 1
            if player2_name:
                data['users'][player2_name]['losses'] += 1
            winner_name = player1_name
        elif result_override == 'player2_win':
            data['users'][player1_name]['losses'] += 1
            if player2_name:
                data['users'][player2_name]['wins'] += 1
            winner_name = player2_name or 'N/A'
        elif player2_name and player1_score == player2_score:
            data['users'][player1_name]['draws'] += 1
            data['users'][player2_name]['draws'] += 1
            winner_name = 'DRAW'
        elif player1_score > player2_score or not player2_name:
            data['users'][player1_name]['wins'] += 1
            if player2_name:
                data['users'][player2_name]['losses'] += 1
            winner_name = player1_name
        else:
            data['users'][player1_name]['losses'] += 1
            if player2_name:
                data['users'][player2_name]['wins'] += 1
            winner_name = player2_name or 'N/A'

        data['users'][player1_name]['total_score'] += player1_score
        data['users'][player1_name]['games_played'] += 1

        if player2_name:
            data['users'][player2_name]['total_score'] += player2_score
            data['users'][player2_name]['games_played'] += 1

        data['games'].append({
            'player1': player1_name,
            'score1': player1_score,
            'player2': player2_name,
            'score2': player2_score,
            'winner': winner_name,
            'timestamp': _now_iso()
        })

        _save_data_unlocked(data)
        return data['users'][player1_name]


def get_leaderboard():
    """리더보드 조회"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        users = [dict(row) for row in data['users'].values()]
        for u in users:
            u.setdefault('draws', 0)
        users.sort(key=lambda x: (x['wins'], x['draws'], x['total_score']), reverse=True)
        return users


def get_recent_games(limit=10, username=None):
    with DATA_LOCK:
        data = _load_data_unlocked()
        trimmed_limit = _clamp_limit(limit, default=10, maximum=50)
        recent_games = []

        for game in _sorted_games_desc(data.get('games', [])):
            if username and username not in {game.get('player1'), game.get('player2')}:
                continue
            entry = _serialize_game_entry(game, username=username)
            if entry is not None:
                recent_games.append(entry)
            if len(recent_games) >= trimmed_limit:
                break

        return recent_games


def save_single_leaderboard(username, score):
    """싱글 랭킹 저장"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        score = _coerce_int(score)
        entry = {
            'username': username,
            'score': score,
            'timestamp': _now_iso()
        }
        data['single_leaderboard'].append(entry)
        data['single_leaderboard'] = sorted(
            data['single_leaderboard'], key=lambda x: x['score'], reverse=True
        )[:20]
        _save_data_unlocked(data)
        return True


def get_single_leaderboard():
    """싱글 랭킹 조회"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        return [
            dict(row)
            for row in sorted(data.get('single_leaderboard', []), key=lambda x: x['score'], reverse=True)
        ]


def reset_leaderboard():
    """리더보드 및 게임 기록 초기화"""
    with DATA_LOCK:
        data = _default_data()
        _save_data_unlocked(data)
    return True


def get_user_stats(username):
    """특정 사용자 통계"""
    with DATA_LOCK:
        data = _load_data_unlocked()
        user = data['users'].get(username)
        return dict(user) if user else None


def get_user_profile(username, recent_limit=5):
    with DATA_LOCK:
        data = _load_data_unlocked()
        user = data['users'].get(username)
        if not user:
            return None

        users = [dict(row) for row in data['users'].values()]
        for row in users:
            row.setdefault('draws', 0)
        users.sort(key=lambda row: (row['wins'], row['draws'], row['total_score']), reverse=True)

        rank = next(
            (index + 1 for index, row in enumerate(users) if row.get('username') == username),
            None,
        )

        recent_games = []
        for game in _sorted_games_desc(data.get('games', [])):
            if username not in {game.get('player1'), game.get('player2')}:
                continue
            entry = _serialize_game_entry(game, username=username)
            if entry is not None:
                recent_games.append(entry)
            if len(recent_games) >= _clamp_limit(recent_limit, default=5, maximum=10):
                break

        games_played = user.get('games_played', 0) or 0
        wins = user.get('wins', 0) or 0
        draws = user.get('draws', 0) or 0
        losses = user.get('losses', 0) or 0
        total_score = user.get('total_score', 0) or 0
        recent_form = [
            {'win': 'W', 'loss': 'L', 'draw': 'D'}.get(game.get('result'), '?')
            for game in recent_games
        ]

        return {
            'username': username,
            'rank': rank,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'games_played': games_played,
            'total_score': total_score,
            'avg_score': round(total_score / games_played, 1) if games_played else 0.0,
            'win_rate': round((wins / games_played) * 100, 1) if games_played else 0.0,
            'created_at': user.get('created_at'),
            'last_played_at': recent_games[0].get('timestamp') if recent_games else None,
            'current_streak': _current_streak(recent_games),
            'recent_form': recent_form,
            'recent_games': recent_games,
        }
