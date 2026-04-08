import os
import random
import string
import time
import psutil
import secrets
import re
import hmac
from flask import Flask, render_template, jsonify, request
import yacht_engine
import database

app = Flask(__name__)

# 메모리 내 데이터 저장소
rooms = {}
# lobby_clients: { client_id: { 'last_seen': time, 'username': name } }
lobby_clients = {}
CLIENT_TIMEOUT = 45  # 45초 미활동 클라이언트 정리
PLAYER_ROOM_TIMEOUT = 35
OBSERVER_ROOM_TIMEOUT = 90
USERNAME_RE = re.compile(r"^[A-Za-z0-9가-힣_]{2,12}$")
RESET_ADMIN_TOKEN = os.getenv("YACHT_ADMIN_TOKEN", "").strip()

# 캐시 방지 설정
@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
        response.headers.pop('Pragma', None)
        response.headers.pop('Expires', None)
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        response.headers['Cache-Control'] = 'no-cache, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def _normalize_username(raw):
    username = (raw or "").strip()
    if not USERNAME_RE.fullmatch(username):
        return None
    return username

def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _issue_player_token():
    return secrets.token_urlsafe(24)

def _is_valid_player(room, username, player_token):
    if not username or not player_token:
        return False
    expected = room.get("player_tokens", {}).get(username)
    return bool(expected) and hmac.compare_digest(expected, player_token)

def _normalize_dice(dice):
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

def _normalize_kept(kept):
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

def _default_room_state():
    return {
        "dice": [1, 1, 1, 1, 1],
        "kept": [0, 0, 0, 0, 0],
        "rolls_left": 3,
        "scores": {},
        "player_dice": {},
        "player_kept": {},
        "player_rolls_left": {},
        "turn": None,
        "turn_start_time": None,
        "game_over": False,
        "ai_msg": "AI: 새 게임을 시작하세요",
        "ai_rec": None,
        "version": 0,
        "updated_by": None,
        "winner": None,
        "loser": None,
        "end_reason": None,
    }

def _score_total(card):
    card = card or []
    card = (card + [None] * 12)[:12]
    upper = sum((v or 0) for v in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((v or 0) for v in card[6:])
    return upper + bonus + lower

def _room_phase(room):
    state = room.get("state", {})
    if state.get("game_over"):
        return "finished"
    if len(room.get("players", [])) >= 2:
        return "playing"
    return "waiting"

def _touch_player(room, username, now=None):
    now = now or time.time()
    room.setdefault("player_last_seen", {})[username] = now
    room["last_update"] = now

def _touch_observer(room, username, now=None):
    now = now or time.time()
    room.setdefault("observer_last_seen", {})[username] = now
    room["last_update"] = now

def _remove_player(room, username, now=None):
    now = now or time.time()
    if username in room.get("players", []):
        room["players"].remove(username)
    room.get("player_tokens", {}).pop(username, None)
    room.setdefault("player_last_seen", {}).pop(username, None)
    if room.get("host") == username:
        room["host"] = room["players"][0] if room.get("players") else username
    room["last_update"] = now

def _remove_observer(room, username, now=None):
    now = now or time.time()
    if username in room.get("observers", []):
        room["observers"].remove(username)
    room.setdefault("observer_last_seen", {}).pop(username, None)
    room["last_update"] = now

def _finalize_room_forfeit(room, winner, loser, updated_by="system", now=None):
    if not winner or not loser or winner == loser or not room.get("started_full"):
        return
    state = room.get("state")
    if not isinstance(state, dict) or state.get("game_over"):
        return

    scores = state.get("scores", {})
    state["players"] = room.get("players", [])
    state["turn"] = winner
    state["turn_start_time"] = None
    state["game_over"] = True
    state["version"] = state.get("version", 0) + 1
    state["updated_by"] = updated_by
    state["winner"] = winner
    state["loser"] = loser
    if updated_by == "system_timeout":
        state["end_reason"] = "timeout"
    elif updated_by == "system_leave":
        state["end_reason"] = "leave"
    else:
        state["end_reason"] = "system"
    room["state"] = state
    room["last_update"] = now or time.time()

    database.save_game_result(
        winner,
        _score_total(scores.get(winner)),
        loser,
        _score_total(scores.get(loser)),
        result_override='player1_win'
    )

def _prune_room_activity(code, room, now=None):
    now = now or time.time()

    player_last_seen = room.setdefault('player_last_seen', {})
    current_players = list(room.get('players', []))
    stale_players = [
        player for player in current_players
        if player_last_seen.get(player, 0) < now - PLAYER_ROOM_TIMEOUT
    ]
    surviving_players = [player for player in current_players if player not in stale_players]
    for player in stale_players:
        _remove_player(room, player, now)

    if len(current_players) >= 2 and len(stale_players) == 1 and len(surviving_players) == 1:
        _finalize_room_forfeit(
            room,
            surviving_players[0],
            stale_players[0],
            updated_by="system_timeout",
            now=now,
        )

    observer_last_seen = room.setdefault('observer_last_seen', {})
    stale_observers = [
        observer for observer in list(room.get('observers', []))
        if observer_last_seen.get(observer, 0) < now - OBSERVER_ROOM_TIMEOUT
    ]
    for observer in stale_observers:
        _remove_observer(room, observer, now)

    state = room.get('state')
    if isinstance(state, dict):
        state['players'] = room.get('players', [])

    if len(room.get('players', [])) == 0:
        rooms.pop(code, None)
        return None
    room["last_update"] = now
    return room

# --- 라우트 (페이지) ---
@app.route('/')
def index():
    return render_template('lobby.html')

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/game/single')
def game_single():
    return render_template('single-game.html')

@app.route('/game/multi')
def game_multi():
    return render_template('multi-game.html')

# --- API ---

@app.route('/api/lobby-heartbeat', methods=['POST'])
def lobby_heartbeat():
    try:
        data = request.json or {}
        client_id = (data.get('client_id') or '')[:64]
        username = _normalize_username(data.get('username')) or '익명'

        if not client_id:
            return jsonify({"error": "client_id required"}), 400

        # 접속 정보 갱신
        lobby_clients[client_id] = {
            'last_seen': time.time(),
            'username': username
        }

        # 만료된 클라이언트 정리
        now = time.time()
        to_remove = []
        for cid, info in lobby_clients.items():
            last_seen = info['last_seen'] if isinstance(info, dict) else info
            if now - last_seen > CLIENT_TIMEOUT:
                to_remove.append(cid)

        for cid in to_remove:
            del lobby_clients[cid]

        return jsonify({"status": "ok", "active_clients": len(lobby_clients)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [추가된 API] 로비 유저 상태(게임중/대기중) 통합 반환
@app.route('/api/online-users', methods=['GET'])
def online_users():
    now = time.time()

    # 1. 대기실 유저 (Heartbeat 기준)
    lobby = {}
    for cid, info in lobby_clients.items():
        if isinstance(info, dict) and now - info['last_seen'] <= CLIENT_TIMEOUT:
            uname = info.get('username', '알 수 없음')
            if uname:
                lobby[uname] = {'status': '대기중'}

    # 2. 게임중 유저 (Rooms 기준)
    playing = {}
    for code, room in rooms.items():
        for p in room.get('players', []):
            if p:
                playing[p] = {'status': '게임중', 'room': code}

    # 3. 통합 (게임중 상태가 대기중보다 우선)
    all_users = {}
    all_users.update(lobby)
    all_users.update(playing)

    # 4. 리스트 변환
    result = []
    for uname, meta in all_users.items():
        entry = {'username': uname, 'status': meta['status']}
        if 'room' in meta:
            entry['room'] = meta['room']
        result.append(entry)

    return jsonify(result)

# 기존 호환성 유지용 (lobby_users)
@app.route('/api/lobby-users', methods=['GET'])
def lobby_users():
    now = time.time()
    users = []
    for cid, info in lobby_clients.items():
        if isinstance(info, dict) and now - info['last_seen'] <= CLIENT_TIMEOUT:
            users.append({
                "client_id": cid,
                "username": info.get('username', '익명')
            })
    return jsonify(users)

@app.route('/api/system-status')
def system_status():
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        now = time.time()
        active_count = 0
        to_remove = []

        for cid, info in lobby_clients.items():
            try:
                last_seen = info['last_seen'] if isinstance(info, dict) else info
                if now - last_seen <= CLIENT_TIMEOUT:
                    active_count += 1
                else:
                    to_remove.append(cid)
            except:
                to_remove.append(cid)

        for cid in to_remove:
            lobby_clients.pop(cid, None)

        return jsonify({
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "online_count": active_count,
            "active_rooms": len(rooms)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommend', methods=['POST'])
def recommend():
    try:
        started = time.perf_counter()
        data = request.json or {}
        dice = data.get('dice', [])
        rolls_left = data.get('rolls_left', 0)
        scorecard = data.get('scorecard', [])
        strategy_mode = data.get('strategy_mode', 'focused')
        open_categories = [i for i, score in enumerate(scorecard) if score is None]

        if not open_categories or rolls_left < 0:
            return jsonify({"message": "추천 불가", "keep_indices": [], "dice_recommendations": []})

        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories, strategy_mode, scorecard)
        elapsed_ms = (time.perf_counter() - started) * 1000
        cache_info = yacht_engine.get_solver_cache_info()
        response = jsonify(result)
        response.headers['X-AI-Elapsed-Ms'] = f"{elapsed_ms:.2f}"
        response.headers['X-AI-Cache-Hits'] = str(cache_info.hits)
        response.headers['X-AI-Cache-Misses'] = str(cache_info.misses)
        return response
    except Exception as e:
        return jsonify({"error": str(e), "message": "AI 추천 오류"}), 500

# --- 리더보드 & 게임 데이터 ---
@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    return jsonify(database.get_leaderboard())

@app.route('/api/leaderboard/single', methods=['GET'])
def leaderboard_single():
    return jsonify(database.get_single_leaderboard())

@app.route('/api/leaderboard/single', methods=['POST'])
def leaderboard_single_post():
    data = request.json or {}
    username = _normalize_username(data.get('username'))
    score = data.get('score')
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = None
    if not username or score is None or score < 0 or score > 1000:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400
    database.save_single_leaderboard(username, score)
    return jsonify({'success': True})

@app.route('/api/leaderboard/multi', methods=['GET'])
def leaderboard_multi():
    return jsonify(database.get_leaderboard())

@app.route('/api/leaderboard/reset', methods=['POST'])
def reset_leaderboard():
    admin_token = request.headers.get('X-Admin-Token', '')
    if not RESET_ADMIN_TOKEN:
        return jsonify({"error": "관리자 토큰이 설정되지 않았습니다"}), 503
    if not hmac.compare_digest(admin_token, RESET_ADMIN_TOKEN):
        return jsonify({"error": "권한 없음"}), 403
    database.reset_leaderboard()
    return jsonify({"status": "reset"})

@app.route('/api/save-game', methods=['POST'])
def save_game():
    try:
        data = request.json or {}
        player1 = _normalize_username(data.get('player1'))
        player2 = _normalize_username(data.get('player2')) if data.get('player2') else None
        score1 = int(data.get('score1', 0))
        score2 = int(data.get('score2', 0))
        if not player1:
            return jsonify({"error": "player1 required"}), 400
        database.save_game_result(player1, score1, player2, score2)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 방 관리 API ---
def _generate_room_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

@app.route('/api/rooms', methods=['GET'])
def list_rooms():
    now = time.time()
    for code, info in list(rooms.items()):
        _prune_room_activity(code, info, now)

    return jsonify([
        {
            "code": code,
            "host": info["host"],
            "players": info["players"],
            "status": "full" if len(info["players"]) >= 2 else "waiting",
            "room_phase": _room_phase(info),
            "observer_count": len(info.get("observers", [])),
        }
        for code, info in rooms.items() if len(info.get("players", [])) >= 1
    ])

@app.route('/api/rooms', methods=['POST'])
def create_room():
    username = _normalize_username((request.json or {}).get('username'))
    if not username:
        return jsonify({"error": "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"}), 400

    code = _generate_room_code()
    while code in rooms: code = _generate_room_code()
    now = time.time()

    base_state = _default_room_state()
    base_state["scores"][username] = [None] * 12
    base_state["player_dice"][username] = [1]*5
    base_state["player_kept"][username] = [0]*5
    base_state["player_rolls_left"][username] = 3
    base_state["turn"] = username
    base_state["players"] = [username]

    player_token = _issue_player_token()
    rooms[code] = {
        "host": username,
        "players": [username],
        "observers": [],
        "player_tokens": {username: player_token},
        "state": base_state,
        "created_at": now,
        "last_update": now,
        "started_full": False,
        "player_last_seen": {username: now},
        "observer_last_seen": {},
    }
    return jsonify({"code": code, "players": rooms[code]["players"], "player_token": player_token})

@app.route('/api/rooms/<code>/join', methods=['POST'])
def join_room(code):
    username = _normalize_username((request.json or {}).get('username'))
    if not username:
        return jsonify({"error": "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"}), 400
    if code not in rooms: return jsonify({"error": "방 없음"}), 404

    now = time.time()
    room = _prune_room_activity(code, rooms[code], now)
    if not room:
        return jsonify({"error": "방 없음"}), 404
    if username in room["players"]:
        return jsonify({"error": "이미 사용 중인 닉네임입니다"}), 409
    if len(room["players"]) >= 2:
        return jsonify({"error": "방이 가득 찼습니다"}), 409
    room["players"].append(username)
    player_token = _issue_player_token()
    room.setdefault("player_tokens", {})[username] = player_token

    state = _default_room_state()
    host = room["players"][0]
    guest = username

    state["scores"] = {host: [None]*12, guest: [None]*12}
    state["player_dice"] = {host: [1]*5, guest: [1]*5}
    state["player_kept"] = {host: [0]*5, guest: [0]*5}
    state["player_rolls_left"] = {host: 3, guest: 3}
    state["players"] = room["players"]
    state["turn"] = host
    state["turn_start_time"] = time.time()
    state["version"] = (room.get("state", {}).get("version", 0)) + 1
    state["updated_by"] = "system"

    room["state"] = state
    room["last_update"] = now
    room["started_full"] = True
    _touch_player(room, username, now)

    return jsonify({
        "code": code,
        "players": room["players"],
        "state": room["state"],
        "observers": room.get("observers", []),
        "player_token": player_token,
    })

@app.route('/api/rooms/<code>/observe', methods=['POST'])
def observe_room(code):
    username = _normalize_username((request.json or {}).get('username'))
    if not username:
        return jsonify({"error": "닉네임은 2~12자(한글/영문/숫자/_)만 가능합니다"}), 400
    if code not in rooms: return jsonify({"error": "방 없음"}), 404

    now = time.time()
    room = _prune_room_activity(code, rooms[code], now)
    if not room:
        return jsonify({"error": "방 없음"}), 404
    if username in room["players"]:
        return jsonify({"error": "이미 플레이어입니다"}), 409

    if username not in room.get("observers", []):
        room.setdefault("observers", []).append(username)
    _touch_observer(room, username, now)

    return jsonify({"code": code, "observers": room["observers"], "players": room["players"], "state": room["state"]})

@app.route('/api/rooms/<code>', methods=['GET'])
def get_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404

    now = time.time()
    u = request.args.get('u')
    pt = request.args.get('pt')
    if u and (u in room.get('players', [])) and _is_valid_player(room, u, pt):
        _touch_player(room, u, now)
    elif u and u in room.get('observers', []):
        _touch_observer(room, u, now)

    room = _prune_room_activity(code, room, now)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", _default_room_state())
    turn_left = None
    if state.get("turn_start_time"):
        turn_left = max(0, 30 - int(now - state["turn_start_time"]))
    state_payload = dict(state)
    state_payload["turn_left_seconds"] = turn_left
    since_version = _safe_int(request.args.get('sv'))
    current_version = _safe_int(state.get("version"), 0)

    p1 = room["host"]
    p2 = None
    for p in room["players"]:
        if p != p1:
            p2 = p
            break

    payload = {
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "observers": room.get("observers", []),
        "observer_count": len(room.get("observers", [])),
        "room_phase": _room_phase(room),
        "state": state_payload,
        "player1": p1,
        "player2": p2
    }
    if since_version is not None and since_version == current_version:
        payload["unchanged"] = True
        payload["state"] = {
            "version": current_version,
            "turn_left_seconds": turn_left,
            "turn": state.get("turn"),
            "game_over": state.get("game_over", False),
        }
    return jsonify(payload)

@app.route('/api/rooms/<code>/heartbeat', methods=['POST'])
def heartbeat_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    data = request.json or {}
    username = _normalize_username(data.get('username'))
    player_token = data.get('player_token')
    now = time.time()

    if username in room.get("players", []):
        if not _is_valid_player(room, username, player_token):
            return jsonify({"error": "참가자 인증 실패"}), 403
        _touch_player(room, username, now)
    elif username in room.get("observers", []):
        _touch_observer(room, username, now)
    else:
        return jsonify({"error": "참가자 없음"}), 404

    room = _prune_room_activity(code, room, now)
    if not room:
        return jsonify({"error": "방 없음"}), 404

    return jsonify({
        "status": "ok",
        "room_phase": _room_phase(room),
        "observer_count": len(room.get("observers", [])),
    })

@app.route('/api/rooms/<code>/sync', methods=['POST'])
def sync_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.json or {}
    username = _normalize_username(data.get('username'))
    player_token = data.get('player_token')
    if username not in room["players"] or not _is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403
    now = time.time()
    _touch_player(room, username, now)
    room = _prune_room_activity(code, room, now)
    if not room or username not in room.get("players", []):
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username and not data.get("game_over"):
        return jsonify({"error": "상대 턴"}), 403

    dice = _normalize_dice(data.get("dice", state["dice"]))
    kept = _normalize_kept(data.get("kept", state["kept"]))
    if dice is None or kept is None:
        return jsonify({"error": "잘못된 주사위 데이터"}), 400
    rolls_left = data.get("rolls_left", state["rolls_left"])

    state.setdefault("player_dice", {})[username] = dice
    state.setdefault("player_kept", {})[username] = kept
    state.setdefault("player_rolls_left", {})[username] = rolls_left

    prev_turn = state.get("turn")
    new_turn = data.get("turn", state.get("turn"))

    turn_start_time = state.get("turn_start_time")
    if (prev_turn != new_turn) or (rolls_left == 3 and state.get("rolls_left") != 3):
        turn_start_time = time.time()

    is_game_over = data.get("game_over", state["game_over"])
    new_state = {
        "dice": dice,
        "kept": kept,
        "rolls_left": rolls_left,
        "scores": data.get("scores", state["scores"]),
        "player_dice": state.get("player_dice", {}),
        "player_kept": state.get("player_kept", {}),
        "player_rolls_left": state.get("player_rolls_left", {}),
        "turn": new_turn,
        "turn_start_time": turn_start_time,
        "game_over": is_game_over,
        "ai_rec": data.get("ai_rec", state.get("ai_rec")),
        "players": state.get("players", room["players"]),
        "version": state.get("version", 0) + 1,
        "updated_by": username,
        "winner": data.get("winner", state.get("winner")),
        "loser": data.get("loser", state.get("loser")),
        "end_reason": data.get("end_reason", state.get("end_reason")),
    }
    if not is_game_over:
        new_state["winner"] = None
        new_state["loser"] = None
        new_state["end_reason"] = None
    room["state"] = new_state
    room["last_update"] = now
    return jsonify({"state": new_state})

@app.route('/api/rooms/<code>/roll', methods=['POST'])
def roll_dice(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.json or {}
    username = _normalize_username(data.get('username'))
    player_token = data.get('player_token')
    if username not in room["players"] or not _is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403
    now = time.time()
    _touch_player(room, username, now)
    room = _prune_room_activity(code, room, now)
    if not room or username not in room.get("players", []):
        return jsonify({"error": "방 없음"}), 404

    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username:
        return jsonify({"error": "상대 턴"}), 403

    rolls_left = state.get("rolls_left", 3)
    if rolls_left <= 0: return jsonify({"error": "남은 굴림 없음"}), 400

    kept = _normalize_kept(data.get("kept", state["kept"]))
    if kept is None:
        return jsonify({"error": "잘못된 고정 주사위 데이터"}), 400
    new_dice = state["dice"][:]
    for i in range(5):
        if not kept[i]:
            new_dice[i] = secrets.randbelow(6) + 1

    state.setdefault("player_dice", {})[username] = new_dice
    state.setdefault("player_kept", {})[username] = kept
    state["dice"] = new_dice
    state["kept"] = kept
    state["rolls_left"] = rolls_left - 1
    state["version"] = state.get("version", 0) + 1
    state["turn_start_time"] = now

    room["state"] = state
    room["last_update"] = now

    return jsonify({"dice": new_dice, "rolls_left": state["rolls_left"], "state": state})

@app.route('/api/rooms/<code>/leave', methods=['POST', 'GET'])
def leave_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.get_json(silent=True) or {}
    username = _normalize_username(data.get('username') or request.args.get('username'))
    player_token = data.get('player_token') or request.args.get('pt')
    if username in room.get("players", []) and not _is_valid_player(room, username, player_token):
        return jsonify({"error": "참가자 인증 실패"}), 403
    now = time.time()

    if username in room["players"]:
        _remove_player(room, username, now)
        state = room.get("state", _default_room_state())

        if len(room["players"]) > 0:
            winner = room["players"][0]
            _finalize_room_forfeit(room, winner, username, updated_by="system_leave", now=now)
            return jsonify({"status": "left", "players": room["players"]})

    if username in room.get("observers", []):
        _remove_observer(room, username, now)
        return jsonify({
            "status": "left",
            "players": room.get("players", []),
            "observers": room.get("observers", []),
        })

    if len(room.get("players", [])) == 0:
        rooms.pop(code, None)

    return jsonify({"status": "left", "players": []})

@app.route('/health', methods=['GET'])
def healthcheck():
    return jsonify({
        "status": "ok",
        "rooms": len(rooms),
        "lobby_clients": len(lobby_clients),
    })

if __name__ == '__main__':
    print("🎲 Yacht Game Server Running on Port 8080...")
    host = os.getenv("YACHT_HOST", "0.0.0.0")
    port = int(os.getenv("YACHT_PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
