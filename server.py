import os
import random
import string
import requests
import subprocess
import time
import psutil
from flask import Flask, render_template, jsonify, request
import yacht_engine
import database


def _score_total(card):
    card = card or []
    # 카드 길이 보정
    card = (card + [None] * 12)[:12]
    upper = sum((v or 0) for v in card[:6])
    bonus = 35 if upper >= 63 else 0
    lower = sum((v or 0) for v in card[6:])
    return upper + bonus + lower

app = Flask(__name__)
DISCORD_WEBHOOK_URL = "여기에_웹훅_주소"
# In-memory room store for simple friend play
rooms = {}
# Lobby client tracking: {client_id: last_seen_timestamp}
lobby_clients = {}
ROOM_TIMEOUT = 3600  # 1시간 동안 활동이 없는 방은 삭제
CLIENT_TIMEOUT = 30  # 30초 동안 heartbeat 없으면 접속 해제로 간주


# 캐시 방지 미들웨어
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
        "scores": {},  # username -> score list
        "player_dice": {},  # username -> dice array (각 플레이어별 주사위 저장)
        "player_kept": {},  # username -> kept array
        "player_rolls_left": {},  # username -> rolls_left
        "turn": None,
        "game_over": False,
        "ai_msg": "AI: 새 게임을 시작하세요",
        "version": 0,
        "updated_by": None,
    }

def clean_inactive_rooms():
    """일정 시간 동안 활동이 없는 방 삭제"""
    current_time = time.time()
    to_delete = []
    for code, room in rooms.items():
        # 마지막 업데이트 시간 체크
        last_update = room.get("last_update", room.get("created_at", current_time))
        if current_time - last_update > ROOM_TIMEOUT:
            to_delete.append(code)
    
    for code in to_delete:
        del rooms[code]
        print(f"방 {code} 자동 삭제 (비활성)")
    
    return len(to_delete)

@app.route('/')
def index():
    return render_template('lobby.html')

@app.route('/game')
def game():
    # 기존 경로 유지 (호환성)
    return render_template('index.html')

@app.route('/game/single')
def game_single():
    return render_template('single-game.html')

@app.route('/game/multi')
def game_multi():
    return render_template('multi-game.html')

@app.route('/api/recommend', methods=['POST'])
def recommend():
    try:
        data = request.json
        dice = data.get('dice', [])
        rolls_left = data.get('rolls_left', 0)
        # scorecard에서 값이 null(빈칸)인 인덱스들만 추출
        scorecard = data.get('scorecard', []) 
        open_categories = [i for i, score in enumerate(scorecard) if score is None]
        
        if not open_categories:
            return jsonify({"message": "게임 종료!", "keep_indices": [], "dice_recommendations": []})

        if rolls_left < 0:
            return jsonify({"message": "오류: 턴 종료", "keep_indices": [], "dice_recommendations": []})

        # 수학 엔진 가동
        result = yacht_engine.solve_best_move(dice, rolls_left, open_categories)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "message": "AI 추천 오류", "dice_recommendations": []}), 500

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({"status": "ok"})

@app.route('/api/leaderboard', methods=['GET'])
def leaderboard():
    return jsonify(database.get_leaderboard())


@app.route('/api/leaderboard/reset', methods=['POST'])
def reset_leaderboard():
    # 간단한 보호: 로컬 테스트용. 필요하면 인증 추가
    database.reset_leaderboard()
    return jsonify({"status": "reset"})


def _generate_room_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


@app.route('/api/rooms', methods=['GET'])
def list_rooms():
    # 하트비트 기준으로 오래된 플레이어 정리 + 0명인 방은 즉시 삭제
    now = time.time()
    to_delete = []
    for code, info in list(rooms.items()):
        pls = info.setdefault('player_last_seen', {})
        stale_threshold = 10.0
        # 하트비트 기록이 있는 플레이어만 정리 (기록이 없으면 대기 중으로 간주)
        stale_players = [p for p in list(info.get('players', [])) if (p in pls) and (pls.get(p, 0) < now - stale_threshold)]
        if stale_players:
            for p in stale_players:
                if p in info['players']:
                    info['players'].remove(p)
            st = info.get('state', _default_room_state())
            st['players'] = info['players']
            info['state'] = st
        if len(info.get('players', [])) == 0:
            to_delete.append(code)
    for code in to_delete:
        del rooms[code]

    # 모든 방 노출 (빈 방 제외, 진행 중인 게임도 표시)
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
        # 새 게임 시작: 이전 게임 기록 초기화 (두 번째 플레이어 입장 시 게임 리셋)
        old_state = room.get("state", _default_room_state())
        state = _default_room_state()
        host = room["players"][0]
        guest = username
        # 두 플레이어 모두 초기화
        state["scores"] = {host: [None] * 12, guest: [None] * 12}
        state["player_dice"] = {host: [1, 1, 1, 1, 1], guest: [1, 1, 1, 1, 1]}
        state["player_kept"] = {host: [0, 0, 0, 0, 0], guest: [0, 0, 0, 0, 0]}
        state["player_rolls_left"] = {host: 3, guest: 3}
        state["players"] = room["players"]
        state["turn"] = host  # 호스트가 먼저 시작
        state["game_over"] = False
        state["ai_msg"] = "AI: 새 게임을 시작하세요"
        state["version"] = old_state.get("version", 0) + 1  # 버전 증가로 강제 업데이트
        state["updated_by"] = "system"
        room["state"] = state
        room["last_update"] = time.time()
        room["started_full"] = True  # 두 명이 된 적 있음
        room.setdefault("player_last_seen", {})[username] = time.time()
    return jsonify({"code": code, "players": room["players"], "state": room["state"]})


@app.route('/api/rooms/<code>', methods=['GET'])
def get_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    now = time.time()
    u = request.args.get('u')
    if u and u in room.get('players', []):
        room.setdefault('player_last_seen', {})[u] = now
        room['last_update'] = now

    # Stale detection: prune stale players; 0명이 되면 방 삭제
    pls = room.setdefault('player_last_seen', {})
    stale_threshold = 10.0
    # 하트비트 기록이 있는 경우에만 오래된 것으로 간주
    stale_players = [p for p in list(room.get('players', [])) if (p in pls) and (pls.get(p, 0) < now - stale_threshold)]
    if stale_players:
        for p in stale_players:
            if p in room['players']:
                room['players'].remove(p)
        if len(room['players']) == 0:
            del rooms[code]
            return jsonify({"error": "방을 찾을 수 없습니다"}), 404
        # keep state players in sync
        st = room.get('state', _default_room_state())
        st['players'] = room['players']
        room['state'] = st

    return jsonify({
        "code": code,
        "host": room["host"],
        "players": room["players"],
        "state": room.get("state", _default_room_state()),
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
    state.setdefault("players", room["players"])
    state["scores"].setdefault(username, [None] * 12)

    # 턴 주인만 상태를 갱신할 수 있도록 제한 (단, 게임 종료 알림은 누구나 가능)
    if state.get("turn") and state["turn"] != username and not data.get("game_over"):
        return jsonify({"error": "상대 턴입니다", "turn": state["turn"]}), 403

    # 주사위 값 검증
    dice = data.get("dice", state["dice"])
    if not isinstance(dice, list) or len(dice) != 5 or not all(isinstance(d, int) and 1 <= d <= 6 for d in dice):
        return jsonify({"error": "유효하지 않은 주사위 값"}), 400
    kept = data.get("kept", state["kept"])
    if not isinstance(kept, list) or len(kept) != 5 or not all(k in [0, 1] for k in kept):
        return jsonify({"error": "유효하지 않은 kept 값"}), 400
    rolls_left = data.get("rolls_left", state["rolls_left"])
    if not isinstance(rolls_left, int) or rolls_left < 0 or rolls_left > 3:
        return jsonify({"error": "유효하지 않은 rolls_left 값"}), 400

    # 플레이어별 주사위 정보 저장
    state.setdefault("player_dice", {})[username] = dice
    state.setdefault("player_kept", {})[username] = kept
    state.setdefault("player_rolls_left", {})[username] = rolls_left

    incoming_version = state.get("version", 0) + 1
    new_state = {
        "dice": dice,
        "kept": kept,
        "rolls_left": rolls_left,
        "scores": data.get("scores", state["scores"]),
        "player_dice": state.get("player_dice", {}),
        "player_kept": state.get("player_kept", {}),
        "player_rolls_left": state.get("player_rolls_left", {}),
        "turn": data.get("turn", state.get("turn")),
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
    """서버에서 주사위를 굴림 (클라이언트 조작 방지)"""
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    
    data = request.json or {}
    username = data.get('username')
    if username not in room["players"]:
        # 이미 제거됐거나 이름이 일치하지 않는 경우: 방은 자동 삭제하지 않음
        return jsonify({"status": "left", "players": room.get("players", [])})
    
    state = room.get("state", _default_room_state())
    
    # 턴 주인만 주사위를 굴릴 수 있음
    if state.get("turn") and state["turn"] != username:
        return jsonify({"error": "상대 턴입니다", "turn": state["turn"]}), 403
    
    # rolls_left 검증 (서버에서 계산한 값 사용, 클라이언트 값 무시)
    rolls_left = state.get("rolls_left", 3)
    if rolls_left <= 0:
        return jsonify({"error": "남은 굴림이 없습니다"}), 400
    
    # kept 검증
    kept = data.get("kept", state["kept"])
    if not isinstance(kept, list) or len(kept) != 5 or not all(k in [0, 1] for k in kept):
        return jsonify({"error": "유효하지 않은 kept 값"}), 400
    
    # 서버에서 직접 주사위 굴림 (플레이어별 주사위로 저장)
    player_dice = state.setdefault("player_dice", {})
    player_kept = state.setdefault("player_kept", {})
    player_rolls_left = state.setdefault("player_rolls_left", {})

    # 현재 플레이어의 기존 주사위 상태를 기반으로 굴림
    base_dice = player_dice.get(username, state.get("dice", [1, 1, 1, 1, 1]))
    new_dice = base_dice[:]
    for i in range(5):
        if not kept[i]:  # kept되지 않은 주사위만 굴림
            new_dice[i] = random.randint(1, 6)
    
    # 상태 업데이트 (rolls_left는 서버에서만 관리)
    player_dice[username] = new_dice
    player_kept[username] = kept
    player_rolls_left[username] = player_rolls_left.get(username, 3) - 1

    # 기존 필드도 현재 턴 주인의 상태로 유지 (호환성)
    state["dice"] = new_dice
    state["kept"] = kept
    state["rolls_left"] = player_rolls_left[username]
    state["version"] = state.get("version", 0) + 1
    state["updated_by"] = username
    room["state"] = state
    room["last_update"] = time.time()
    
    return jsonify({"dice": new_dice, "rolls_left": state["rolls_left"], "state": state})

@app.route('/api/rooms/<code>/leave', methods=['POST', 'GET'])
def leave_room(code):
    room = rooms.get(code)
    if not room:
        return jsonify({"error": "방을 찾을 수 없습니다"}), 404
    data = request.get_json(silent=True) or {}
    username = data.get('username') or request.args.get('username')
    if username not in room["players"]:
        return jsonify({"error": "방 참가자가 아닙니다"}), 403
    
    # 플레이어 제거
    room["players"].remove(username)
    state = room.get("state", _default_room_state())

    # 남은 플레이어가 있으면 승리 처리만 하고 방은 유지 (마지막 남은 유저가 나갈 때 방 삭제)
    if len(room["players"]) > 0:
        winner = room["players"][0]
        loser = username
        # 승패 기록 유지
        state["game_over"] = True
        state["ai_msg"] = f"🎮 연결 종료: {username}님이 나갔습니다"
        state["version"] = state.get("version", 0) + 1
        state["updated_by"] = "system"
        state["players"] = room["players"]

        # 전적 저장 (기록되지 않던 중도 퇴실 케이스 처리)
        scores = state.get("scores", {})
        winner_card = scores.get(winner, [None] * 12)
        loser_card = scores.get(loser, [None] * 12)
        winner_total = _score_total(winner_card)
        loser_total = _score_total(loser_card)
        database.save_game_result(winner, winner_total, loser, loser_total)

        room["state"] = state
        room["last_update"] = time.time()
        return jsonify({"status": "left", "players": room.get("players", [])})

    # 마지막 유저가 나간 경우에만 방 삭제
    rooms.pop(code, None)
    return jsonify({"status": "left", "players": []})

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
    print("🌐 Open http://localhost:8080 in your browser")
    app.run(host='0.0.0.0', port=8080, debug=True)