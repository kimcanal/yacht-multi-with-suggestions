import json
import os
from datetime import datetime

DATA_FILE = 'game_data.json'

def load_data():
    """게임 데이터 로드"""
    if not os.path.exists(DATA_FILE):
        # 싱글/멀티 분리 구조로 초기화
        return {'users': {}, 'games': [], 'single_leaderboard': []}
    try:
        data = json.load(open(DATA_FILE, 'r', encoding='utf-8'))
        # 마이그레이션: single_leaderboard 필드가 없으면 추가
        if 'single_leaderboard' not in data:
            data['single_leaderboard'] = []
        return data
    except:
        return {'users': {}, 'games': [], 'single_leaderboard': []}

def save_data(data):
    """게임 데이터 저장"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_or_create_user(username):
    """사용자 생성/조회"""
    data = load_data()
    if username not in data['users']:
        data['users'][username] = {
            'username': username,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'total_score': 0,
            'games_played': 0,
            'created_at': datetime.now().isoformat()
        }
        save_data(data)
    else:
        # 스키마 업그레이드: 누락 필드를 보정
        data['users'][username].setdefault('draws', 0)
        save_data(data)
    return data['users'][username]

def save_game_result(player1_name, player1_score, player2_name, player2_score):
    """게임 결과 저장"""
    data = load_data()
    
    # 플레이어 정보 확인/생성
    get_or_create_user(player1_name)
    if player2_name:
        get_or_create_user(player2_name)
    # 안전하게 필드 보정 (기존 데이터 호환)
    data['users'][player1_name].setdefault('draws', 0)
    if player2_name:
        data['users'][player2_name].setdefault('draws', 0)
    
    # 승무패 결정
    if player2_name and player1_score == player2_score:
        data['users'][player1_name]['draws'] += 1
        data['users'][player2_name]['draws'] += 1
    elif player1_score > player2_score or not player2_name:
        data['users'][player1_name]['wins'] += 1
        if player2_name:
            data['users'][player2_name]['losses'] += 1
    else:
        data['users'][player1_name]['losses'] += 1
        if player2_name:
            data['users'][player2_name]['wins'] += 1
    
    # 통계 업데이트
    data['users'][player1_name]['total_score'] += player1_score
    data['users'][player1_name]['games_played'] += 1
    
    if player2_name:
        data['users'][player2_name]['total_score'] += player2_score
        data['users'][player2_name]['games_played'] += 1
    
    # 게임 기록 저장
    data['games'].append({
        'player1': player1_name,
        'score1': player1_score,
        'player2': player2_name,
        'score2': player2_score,
        'winner': player1_name if (player1_score > player2_score if player2_name else True) else (player2_name or 'N/A'),
        'timestamp': datetime.now().isoformat()
    })
    
    save_data(data)
    return data['users'][player1_name]

def get_leaderboard():
    """리더보드 조회"""

    data = load_data()
    users = list(data['users'].values())
    for u in users:
        u.setdefault('draws', 0)
    users.sort(key=lambda x: (x['wins'], x['draws'], x['total_score']), reverse=True)
    return users

def save_single_leaderboard(username, score):
    """싱글 랭킹 저장"""
    data = load_data()
    entry = {
        'username': username,
        'score': score,
        'timestamp': datetime.now().isoformat()
    }
    data['single_leaderboard'].append(entry)
    # 상위 20개만 유지
    data['single_leaderboard'] = sorted(data['single_leaderboard'], key=lambda x: x['score'], reverse=True)[:20]
    save_data(data)
    return True

def get_single_leaderboard():
    """싱글 랭킹 조회"""
    data = load_data()
    return sorted(data.get('single_leaderboard', []), key=lambda x: x['score'], reverse=True)


def reset_leaderboard():
    """리더보드 및 게임 기록 초기화"""
    data = {'users': {}, 'games': []}
    save_data(data)
    return True

def get_user_stats(username):
    """특정 사용자 통계"""
    data = load_data()
    return data['users'].get(username, None)
