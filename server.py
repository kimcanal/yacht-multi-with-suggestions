import os
import random

import os
import random
import string
import time
import psutil
from flask import Flask, render_template, jsonify, request
import yacht_engine
import database

def _score_total(card):
    card = card or []
    card = (card + [None] * 12)[:12]
    upper = sum((v or 0) for v in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((v or 0) for v in card[6:])
    return upper + bonus + lower

app = Flask(__name__)

# 메모리 내 데이터 저장소
rooms = {}
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

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    return jsonify(database.get_leaderboard())

@app.route('/api/leaderboard/reset', methods=['POST'])
def reset_leaderboard():
    database.reset_leaderboard()
    return jsonify({"status": "reset"})

def _generate_room_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

@app.route('/api/rooms', methods=['GET'])
def list_rooms():
    # 방 목록 조회 시 비활성 플레이어 정리
    now = time.time()
    to_delete = []
    
    for code, info in list(rooms.items()):
        pls = info.setdefault('player_last_seen', {})
        stale_threshold = 10.0
        
        stale_players = [p for p in list(info.get('players', [])) 
                         if (p in pls) and (pls.get(p, 0) < now - stale_threshold)]
        
        if stale_players:
            for p in stale_players:
                if p in info['players']:
                    info['players'].remove(p)
            # 상태 동기화
            st = info.get('state', _default_room_state())
            st['players'] = info['players']
            info['state'] = st
            
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
        for code, info in rooms.items()
        if len(info.get("players", [])) >= 1
    ])

@app.route('/api/rooms', methods=['POST'])
def create_room():
    username = (request.json or {}).get('username')
    if not username:
        return jsonify({"error": "닉네임이 필요합니다"}), 400
    code = _generate_room_code()
    while code in rooms:
        code = _generate_room_code()
        
    base_state = _default_room_state()
    base_state["scores"][username] = [None] * 12
    base_state["player_dice"][username] = [1, 1, 1, 1, 1]
    base_state["player_kept"][username] = [0, 0, 0, 0, 0]
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
    if not username:
        return jsonify({"error": "닉네임이 필요합니다"}), 400
    if code not in rooms:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
        
    room = rooms[code]
    if username not in room["players"]:
        if len(room["players"]) >= 2:
            return jsonify({"error": "방이 가득 찼습니다"}), 409
        room["players"].append(username)
        
        # 2명 모이면 게임 리셋
        old_state = room.get("state", _default_room_state())
        state = _default_room_state()
        host = room["players"][0]
        guest = username
        
        state["scores"] = {host: [None] * 12, guest: [None] * 12}
        state["player_dice"] = {host: [1, 1, 1, 1, 1], guest: [1, 1, 1, 1, 1]}
        state["player_kept"] = {host: [0, 0, 0, 0, 0], guest: [0, 0, 0, 0, 0]}
        state["player_rolls_left"] = {host: 3, guest: 3}
        state["players"] = room["players"]
        state["turn"] = host
        state["turn_start_time"] = time.time()
        state["version"] = old_state.get("version", 0) + 1
        state["updated_by"] = "system"
        
        room["state"] = state
        room["last_update"] = time.time()
        room["started_full"] = True
        room.setdefault("player_last_seen", {})[username] = time.time()
        
    return jsonify({"code": code, "players": room["players"], "state": room["state"], "observers": room.get("observers", [])})

@app.route('/api/rooms/<code>/observe', methods=['POST'])
def observe_room(code):
    username = (request.json or {}).get('username')
    if not username:
        return jsonify({"error": "닉네임이 필요합니다"}), 400
    if code not in rooms:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    room = rooms[code]
    if username in room["players"]:
        return jsonify({"error": "이미 플레이어로 참가 중입니다"}), 409
    if username not in room.get("observers", []):
        room.setdefault("observers", []).append(username)
    return jsonify({"code": code, "observers": room["observers"], "players": room["players"], "state": room["state"]})

@app.route('/api/rooms/<code>', methods=['GET'])
def get_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    
    now = time.time()
    u = request.args.get('u')
    if u and (u in room.get('players', [])):
        room.setdefault('player_last_seen', {})[u] = now
        room['last_update'] = now

    state = room.get("state", _default_room_state())
    turn_left_seconds = None
    if state.get("turn_start_time"):
        turn_left_seconds = max(0, 30 - int(now - state["turn_start_time"]))
    state["turn_left_seconds"] = turn_left_seconds
    
    return jsonify({
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "observers": room.get("observers", []),
        "state": state,
    })

@app.route('/api/rooms/<code>/sync', methods=['POST'])
def sync_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    data = request.json or {}
    username = data.get('username')
    if username not in room["players"]:
        return jsonify({"error": "방 참가자가 아닙니다"}), 403

    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username and not data.get("game_over"):
        return jsonify({"error": "상대 턴입니다"}), 403

    dice = data.get("dice", state["dice"])
    kept = data.get("kept", state["kept"])
    rolls_left = data.get("rolls_left", state["rolls_left"])

    state.setdefault("player_dice", {})[username] = dice
    state.setdefault("player_kept", {})[username] = kept
    state.setdefault("player_rolls_left", {})[username] = rolls_left

    incoming_version = state.get("version", 0) + 1
    
    # 턴 변경 감지 및 타이머 리셋
    prev_turn = state.get("turn")
    new_turn = data.get("turn", state.get("turn"))
    prev_rolls_left = state.get("rolls_left", 3)
    turn_start_time = state.get("turn_start_time")
    
    if (prev_turn != new_turn) or (prev_rolls_left != 3 and rolls_left == 3):
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
        "version": incoming_version,
        "updated_by": username,
    }
    room["state"] = new_state
    room["last_update"] = time.time()
    return jsonify({"state": new_state})

@app.route('/api/rooms/<code>/roll', methods=['POST'])
def roll_dice(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    
    data = request.json or {}
    username = data.get('username')
    if username not in room["players"]:
        return jsonify({"status": "left", "players": room.get("players", [])})
    
    state = room.get("state", _default_room_state())
    if state.get("turn") and state["turn"] != username:
        return jsonify({"error": "상대 턴입니다"}), 403
    
    rolls_left = state.get("rolls_left", 3)
    if rolls_left <= 0:
        return jsonify({"error": "남은 굴림 없음"}), 400
    
    kept = data.get("kept", state["kept"])
    
    player_dice = state.setdefault("player_dice", {})
    player_kept = state.setdefault("player_kept", {})
    player_rolls_left = state.setdefault("player_rolls_left", {})

    base_dice = player_dice.get(username, state.get("dice", [1]*5))
    new_dice = base_dice[:]
    for i in range(5):
        if not kept[i]:
            new_dice[i] = random.randint(1, 6)
    
    player_dice[username] = new_dice
    player_kept[username] = kept
    player_rolls_left[username] = player_rolls_left.get(username, 3) - 1

    state["dice"] = new_dice
    state["kept"] = kept
    state["rolls_left"] = player_rolls_left[username]
    state["version"] = state.get("version", 0) + 1
    state["updated_by"] = username
    state["turn_start_time"] = time.time()
    
    room["state"] = state
    room["last_update"] = time.time()

    return jsonify({"dice": new_dice, "rolls_left": state["rolls_left"], "state": state})

@app.route('/api/rooms/<code>/leave', methods=['POST', 'GET'])
def leave_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방 없음"}), 404
    data = request.get_json(silent=True) or {}
    username = data.get('username') or request.args.get('username')
    
    if username in room["players"]:
        room["players"].remove(username)
        state = room.get("state", _default_room_state())
        
        # 승패 처리
        if len(room["players"]) > 0:
            winner = room["players"][0]
            loser = username
            state["game_over"] = True
            state["version"] += 1
            
            # DB 저장
            scores = state.get("scores", {})
            database.save_game_result(winner, _score_total(scores.get(winner)), loser, _score_total(scores.get(loser)))
            
            room["state"] = state
            return jsonify({"status": "left", "players": room["players"]})

    # 방 삭제
    if len(room.get("players", [])) == 0:
        rooms.pop(code, None)
        
    return jsonify({"status": "left", "players": []})

@app.route('/api/save-game', methods=['POST'])
def save_game():
    try:
        data = request.json
        database.save_game_result(data.get('player1'), data.get('score1', 0), data.get('player2'), data.get('score2', 0))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/lobby-heartbeat', methods=['POST'])
def lobby_heartbeat():
    try:
        data = request.json or {}
        client_id = data.get('client_id')
        if client_id:
            lobby_clients[client_id] = time.time()
        
        now = time.time()
        # 30초 이상 지난 클라이언트 삭제
        expired = [cid for cid, t in lobby_clients.items() if now - t > CLIENT_TIMEOUT]
        for cid in expired:
            del lobby_clients[cid]
            
        return jsonify({"status": "ok", "active_clients": len(lobby_clients)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/system-status')
def system_status():
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        
        now = time.time()
        expired = [cid for cid, t in lobby_clients.items() if now - t > CLIENT_TIMEOUT]
        for cid in expired:
            del lobby_clients[cid]
            
        return jsonify({
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "online_count": len(lobby_clients),
            "active_rooms": len(rooms)
        })
    except Exception:
        return jsonify({"error": "status check failed"}), 500

if __name__ == '__main__':

    print("🎲 Yacht Game Server Running on Port 9999...")
    app.run(host='0.0.0.0', port=8080, debug=True)

@app.route('/api/save-game', methods=['POST'])
def save_game():
    try:
        data = request.json
        player1 = data.get('player1')
        score1 = data.get('score1', 0)
        player2 = data.get('player2')
        score2 = data.get('score2', 0)
        
        database.save_game_result(player1, score1, player2, score2)
        stats = database.get_user_stats(player1)
        
        return jsonify({
            "status": "success",
            "message": "게임 결과가 저장되었습니다",
            "stats": stats
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/<username>', methods=['GET'])
def get_stats(username):
    stats = database.get_user_stats(username)
    if stats:
        return jsonify(stats)
    return jsonify({"error": "사용자를 찾을 수 없습니다"}), 404

@app.route('/reboot', methods=['POST'])
def reboot():
    subprocess.Popen(['sudo', 'reboot'])
    return jsonify({"status": "rebooting"})

@app.route('/api/lobby-heartbeat', methods=['POST'])
def lobby_heartbeat():
    """로비 클라이언트의 heartbeat 수신"""
    try:
        data = request.json or {}
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({"error": "client_id required"}), 400
        
        # 현재 시간 기록
        lobby_clients[client_id] = time.time()
        
        # 오래된 클라이언트 정리 (30초 이상 응답 없음)
        now = time.time()
        expired = [cid for cid, last_seen in lobby_clients.items() 
                   if now - last_seen > CLIENT_TIMEOUT]
        for cid in expired:
            del lobby_clients[cid]
        
        return jsonify({"status": "ok", "active_clients": len(lobby_clients)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/system-status')
def system_status():
    """시스템 상태 정보 반환"""
    try:
        # CPU 사용률
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 메모리 사용률
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024 ** 3)
        memory_total_gb = memory.total / (1024 ** 3)
        
        # 오래된 로비 클라이언트 정리
        now = time.time()
        expired = [cid for cid, last_seen in lobby_clients.items() 
                   if now - last_seen > CLIENT_TIMEOUT]
        for cid in expired:
            del lobby_clients[cid]
        
        # 로비 접속자 수 (최근 30초 내에 heartbeat가 있는 클라이언트)
        online_count = len(lobby_clients)
        active_rooms = len(rooms)
        
        return jsonify({
            "cpu_percent": round(cpu_percent, 1),
            "memory_percent": round(memory_percent, 1),
            "memory_used_gb": round(memory_used_gb, 2),
            "memory_total_gb": round(memory_total_gb, 2),
            "online_count": online_count,
            "active_rooms": active_rooms
        })
    except Exception as e:
        return jsonify({
            "cpu_percent": 0,
            "memory_percent": 0,
            "memory_used_gb": 0,
            "memory_total_gb": 0,
            "online_count": 0,
            "active_rooms": 0,
            "error": str(e)
        }), 500

def send_ngrok_url():
    # ... (이전 코드와 동일, ngrok 주소 디스코드 전송) ...
    pass 

if __name__ == '__main__':
    # ... (ngrok 전송 스레드 실행 부분) ...
    print("🎲 Yacht Game AI Server Starting...")
    print("🌐 External: https://app.yatch-game.cloud")
    print("🌐 Local:    http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)