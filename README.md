# Yacht Dice Game

Flask 기반 웹 요트 다이스 게임 wtih 확률 분석

https://app.yatch-game.cloud/

<img width="706" height="1606" alt="image" src="https://github.com/user-attachments/assets/a3744c82-24be-47e0-ae42-f476fbd7cf0f" />


<img width="1497" height="1159" alt="image" src="https://github.com/user-attachments/assets/62ca51fa-3b80-458c-bff2-683739c4c4fe" />


## 기능

- **싱글플레이 모드**: AI 추천 기능 포함
- **멀티플레이 모드**: 실시간 2인 대전
- **리더보드**: 최고 점수 기록
- **서버 모니터링**: CPU, RAM, 접속자 수 실시간 표시
- **타이머** : 30초 타이머가 돌아갑니다. 시간이 다할시 auto roll이 수행됩니다.

## 설치 및 실행

```bash
# 필요한 패키지 설치
pip3 install flask psutil

# 서버 실행
python3 server.py
```

서버는 기본적으로 `http://localhost:8080`에서 실행됩니다. (Port 8080)

## 게임 규칙
12개 카테고리에 주사위 5개를 굴려 최고 점수를 획득하는 게임입니다.
========================================================================
0123 기준 변경사항
- 싱글 모드시 클라이언트 딴에서 게임이 실행되며, 멀티 모드시 서버 딴에서 게임이 실행됩니다.
- 싱글 모드 시, 남은 롤의 수가 1번 또는 2번일 떄, 타이머가 실행됩니다.
- 멀티 모드 시, 빠른 진행을 위해 남은 롤의 수가 1번 이상인 경우 타이머가 실행됩니다.
- 30초 타이머가 모두 다하면, 타임아웃이 발생하여 '현재 Keep 상태' 에서 자동 롤(auto roll) 이 수행됩니다.
- 주사위를 더이상 돌릴 수 없는, 점수 선택 시간에는 타이머가 없기 때문에 자동 롤이 수행되지 않습니다.

==========================================================================================
0110 기준 주요 변경사항:
 - 싱글/멀티 모두 반응형 UI 개선 (모바일/PC 모두 주사위가 컨테이너에 맞게 가변)
 - 주사위 면과 점(dot) 비율 고정
 - 점수판, 버튼 등 스타일 개선
 - .gitignore에 *.log, *.backup 등 추가
 - Single Straight → Small Straight로 명칭 통일

#### 확률 분석(Suggestions)
- 현재 나온 주사위 눈을 보고, 어느 것들을 KEEP 해야 특정 족보(4 of a Kind, Full House, Single/Large Straight, Yacht)
 달성에 유리한지 추천해줍니다.
- 특정 주사위들을 KEEP 할시 특정 족보 달성 가능성을 플레이어한테 수치 및 그래프로 제시합니다.
- 족보 달성확률이 가장 높은 KEEP 순서쌍을 버튼에 강조합니다.
- 아래 족보를 모두 달성할시, 추가로 얻을 수 있는 One ~ Six의 확률을 플레이어한테 보여줍니다.

### 카테고리
- **Ones ~ Sixes**: 해당 숫자의 합
- **4 of a Kind**: 같은 숫자 4개 이상 (모든 주사위 합, 최대 30점)
- **Full House**: 같은 숫자 3개 + 2개 (모든 주사위 합, 최대 30점)
- **Small Straight**: 연속 4개 (고정 15점, 1-2-3-4, 2-3-4-5, 3-4-5-6)  
- **Large Straight**: 연속 5개 (고정 30점,  1-2-3-4-5, 2-3-4-5-6)
- **Yacht**: 같은 숫자 5개 (50점, 두 번째 Yacht 부터는 보너스 +100점)
- **Choice**: 모든 주사위 합 (최대 30점)

## 기술 스택

- **Backend**: Python 3, Flask
- **Frontend**: HTML, CSS, JavaScript
- **Game Engine**: Python (확률 계산 기반 AI)
- **Monitoring**: psutil

## 파일 구조

```
yacht_game/
├── backup
│   ├── index.html.backup
│   ├── multi-game.html.backup
│   ├── single-game.html_0117 backup
│   └── single-game.html.backup
├── database.py
├── game_data.json
├── __pycache__
│   ├── database.cpython-312.pyc
│   ├── server.cpython-312.pyc
│   └── yacht_engine.cpython-312.pyc
├── README.md
├── server.log
├── server.py
├── static
│   └── js
│       └── yacht_game.js
├── templates
│   ├── index.html
│   ├── lobby.html
│   ├── multi-game.html
│   └── single-game.html
└── yacht_engine.py

6 directories, 18 files
```

## 라이센스

MIT License
