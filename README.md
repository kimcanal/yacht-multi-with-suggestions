# Yacht Dice Game

Flask 기반 웹 요트 다이스 게임

https://app.yatch-game.cloud/

## 기능

- **싱글플레이 모드**: AI 추천 기능 포함
- **멀티플레이 모드**: 실시간 2인 대전
- **리더보드**: 최고 점수 기록
- **서버 모니터링**: CPU, RAM, 접속자 수 실시간 표시

## 설치 및 실행

```bash
# 필요한 패키지 설치
pip3 install flask psutil

# 서버 실행
python3 server.py
```

서버는 기본적으로 `http://localhost:8080`에서 실행됩니다.

## 게임 규칙

13개 카테고리에 주사위 5개를 굴려 최고 점수를 획득하는 게임입니다.
2026.01 기준 주요 변경사항:
 - 싱글/멀티 모두 반응형 UI 개선 (모바일/PC 모두 주사위가 컨테이너에 맞게 가변)
 - 주사위 면과 점(dot) 비율 고정
 - 점수판, 버튼 등 스타일 개선
 - .gitignore에 *.log, *.backup 등 추가
 - Single Straight → Small Straight로 명칭 통일

### 카테고리
- **Ones ~ Sixes**: 해당 숫자의 합
- **4 of a Kind**: 같은 숫자 4개 이상 (모든 주사위 합, 최대 30점)
- **Full House**: 같은 숫자 3개 + 2개 (모든 주사위 합, 최대 30점)
- **Small Straight**: 연속 4개 (15점)  
- **Large Straight**: 연속 5개 (30점)
- **Yacht**: 같은 숫자 5개 (50점, 두 번째는 보너스 +100점)
- **Choice**: 모든 주사위 합 (최대 30점)

## 기술 스택

- **Backend**: Python 3, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Game Engine**: Python (확률 계산 기반 AI)
- **Monitoring**: psutil

## 파일 구조

```
yacht_game/
├── server.py           # Flask 서버
├── yacht_engine.py     # 게임 로직 및 AI
├── database.py         # 리더보드 저장
├── templates/
│   ├── lobby.html      # 메인 페이지
│   └── index.html      # 게임 페이지
└── game_data.json      # 리더보드 데이터
```

## 라이센스

MIT License
