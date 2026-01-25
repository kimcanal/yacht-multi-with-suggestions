import os
import random
import string
import time
import psutil
import secrets
from flask import Flask, render_template, jsonify, request
import yacht_engine
import database

app = Flask(__name__)

# 메모리 내 데이터 저장소
rooms = {}
# lobby_clients: { client_id: { 'last_seen': time, 'username': name } }
lobby_clients = {}
CLIENT_TIMEOUT = 30  # 30초 미활동 클라이언트 정리

# 캐시 방지 설정
@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
        "version": 0,
        "updated_by": None,
    }

def _score_total(card):
    card = card or []
    card = (card + [None] * 12)[:12]
    upper = sum((v or 0) for v in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((v or 0) for v in card[6:])
    return upper + bonus + lower

# --- 라우트 (페이지) ---
@app.route('/')
def index():
    return render_template('lobby.html')

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
        client_id = data.get('client_id')
        username = data.get('username', '익명')
        
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
        data = request.json
        dice = data.get('dice', [])
        rolls_left = data.get('rolls_left', 0)
        scorecard = data.get('scorecard', []) 
        open_categories = [i for i, score in enumerate(scorecard) if score is None]
        
        if not open_categories or rolls_left < 0:
            return jsonify({"message": "추천 불가", "keep_indices": [], "dice_recommendations": []})

        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories)
        return jsonify(result)
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
    username = data.get('username')
    score = data.get('score')
    if not username or score is None:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400
    database.save_single_leaderboard(username, int(score))
    return jsonify({'success': True})

@app.route('/api/leaderboard/multi', methods=['GET'])
def leaderboard_multi():
    return jsonify(database.get_leaderboard())

@app.route('/api/leaderboard/reset', methods=['POST'])
def reset_leaderboard():
    database.reset_leaderboard()
    return jsonify({"status": "reset"})

@app.route('/api/save-game', methods=['POST'])
def save_game():
    try:
        data = request.json
        database.save_game_result(data.get('player1'), data.get('score1', 0), data.get('player2'), data.get('score2', 0))
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
    to_delete = []
    
    for code, info in list(rooms.items()):
        pls = info.setdefault('player_last_seen', {})
        stale_threshold = 10.0
        
        stale_players = [p for p in list(info.get('players', [])) 
                         if (p in pls) and (pls.get(p, 0) < now - stale_threshold)]
        
        if stale_players:
            for p in stale_players:
                if p in info['players']: info['players'].remove(p)
            info['state']['players'] = info['players']
            
        if len(info.get('players', [])) == 0:
            to_delete.append(code)
            
    for code in to_delete:
        del rooms[code]

    return jsonify([
        {
            "code": code,
            "host": info["host"],
            "players": info["players"],
            "status": "full" if len(info["players"]) >= 2 else "waiting",
        }
        for code, info in rooms.items() if len(info.get("players", [])) >= 1
    ])

@app.route('/api/rooms', methods=['POST'])
def create_room():
    username = (request.json or {}).get('username')
    if not username: return jsonify({"error": "닉네임 필요"}), 400
    
    code = _generate_room_code()
    while code in rooms: code = _generate_room_code()
        
    base_state = _default_room_state()
    base_state["scores"][username] = [None] * 12
    base_state["player_dice"][username] = [1]*5
    base_state["player_kept"][username] = [0]*5
    base_state["player_rolls_left"][username] = 3
    base_state["turn"] = username
    base_state["players"] = [username]
    
    rooms[code] = {
        "host": username,
        "players": [username],
        "observers": [],
        "state": base_state,
        "created_at": time.time(),
        "last_update": time.time(),
        "started_full": False,
        "player_last_seen": {username: time.time()},
    }
    return jsonify({"code": code, "players": rooms[code]["players"]})

@app.route('/api/rooms/<code>/join', methods=['POST'])
def join_room(code):
    username = (request.json or {}).get('username')
    if not username: return jsonify({"error": "닉네임 필요"}), 400
    if code not in rooms: return jsonify({"error": "방 없음"}), 404
        
    room = rooms[code]
    if username not in room["players"]:
        if len(room["players"]) >= 2: return jsonify({"error": "방이 가득 찼습니다"}), 409
        room["players"].append(username)
        
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
        room["last_update"] = time.time()
        room["started_full"] = True
        room.setdefault("player_last_seen", {})[username] = time.time()
        
    return jsonify({"code": code, "players": room["players"], "state": room["state"], "observers": room.get("observers", [])})

@app.route('/api/rooms/<code>/observe', methods=['POST'])
def observe_room(code):
    username = (request.json or {}).get('username')
    if not username: return jsonify({"error": "닉네임 필요"}), 400
    if code not in rooms: return jsonify({"error": "방 없음"}), 404
    
    room = rooms[code]
    if username in room["players"]:
        return jsonify({"error": "이미 플레이어입니다"}), 409
        
    if username not in room.get("observers", []):
        room.setdefault("observers", []).append(username)
        
    return jsonify({"code": code, "observers": room["observers"], "players": room["players"], "state": room["state"]})

@app.route('/api/rooms/<code>', methods=['GET'])
def get_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    
    now = time.time()
    u = request.args.get('u')
    if u and (u in room.get('players', [])):
        room.setdefault('player_last_seen', {})[u] = now
        room['last_update'] = now

    state = room.get("state", _default_room_state())
    turn_left = None
    if state.get("turn_start_time"):
        turn_left = max(0, 30 - int(now - state["turn_start_time"]))
    state["turn_left_seconds"] = turn_left
    
    p1 = room["host"]
    p2 = None
    for p in room["players"]:
        if p != p1:
            p2 = p
            break
            
    return jsonify({
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "observers": room.get("observers", []),
        "state": state,
        "player1": p1,
        "player2": p2
    })

@app.route('/api/rooms/<code>/sync', methods=['POST'])
def sync_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.json or {}
    username = data.get('username')
    if username not in room["players"]: return jsonify({"error": "참가자 아님"}), 403

    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username and not data.get("game_over"):
        return jsonify({"error": "상대 턴"}), 403

    dice = data.get("dice", state["dice"])
    kept = data.get("kept", state["kept"])
    rolls_left = data.get("rolls_left", state["rolls_left"])

    state.setdefault("player_dice", {})[username] = dice
    state.setdefault("player_kept", {})[username] = kept
    state.setdefault("player_rolls_left", {})[username] = rolls_left

    prev_turn = state.get("turn")
    new_turn = data.get("turn", state.get("turn"))
    
    turn_start_time = state.get("turn_start_time")
    if (prev_turn != new_turn) or (rolls_left == 3 and state.get("rolls_left") != 3):
        turn_start_time = time.time()

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
        "game_over": data.get("game_over", state["game_over"]),
        "players": state.get("players", room["players"]),
        "version": state.get("version", 0) + 1,
        "updated_by": username,
    }
    room["state"] = new_state
    room["last_update"] = time.time()
    return jsonify({"state": new_state})

@app.route('/api/rooms/<code>/roll', methods=['POST'])
def roll_dice(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.json or {}
    username = data.get('username')
    
    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username:
        return jsonify({"error": "상대 턴"}), 403
    
    rolls_left = state.get("rolls_left", 3)
    if rolls_left <= 0: return jsonify({"error": "남은 굴림 없음"}), 400
    
    kept = data.get("kept", state["kept"])
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
    state["turn_start_time"] = time.time()
    
    room["state"] = state
    room["last_update"] = time.time()
    
    return jsonify({"dice": new_dice, "rolls_left": state["rolls_left"], "state": state})

@app.route('/api/rooms/<code>/leave', methods=['POST', 'GET'])
def leave_room(code):
    room = rooms.get(code)
    if not room: return jsonify({"error": "방 없음"}), 404
    data = request.get_json(silent=True) or {}
    username = data.get('username') or request.args.get('username')
    
    if username in room["players"]:
        room["players"].remove(username)
        state = room.get("state", _default_room_state())
        
        if len(room["players"]) > 0:
            winner = room["players"][0]
            loser = username
            state["game_over"] = True
            state["version"] += 1
            scores = state.get("scores", {})
            database.save_game_result(winner, _score_total(scores.get(winner)), loser, _score_total(scores.get(loser)))
            room["state"] = state
            return jsonify({"status": "left", "players": room["players"]})

    if len(room.get("players", [])) == 0:
        rooms.pop(code, None)
        
    return jsonify({"status": "left", "players": []})

if __name__ == '__main__':
    print("🎲 Yacht Game Server Running on Port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=True)