# AI Recommendation Validation Report (2026-05-21)

사용자 요청("확률이 맞는지 검증")에 맞춰 저장소의 검증 스크립트를 실행해 추천 엔진의 확률 일관성과 안정성을 점검했다.

## 실행한 검증

1. Golden 회귀 검증
- 명령: `python3 scripts/check_ai_golden.py`
- 결과: 7 케이스, 실패 0

2. Soak 확률/일관성 검증
- 명령: `python3 scripts/soak_ai.py --cases 200`
- 결과: 실패 0
- 포함 검증: `cover_success_prob`, `cover_fail_prob` 범위(0~1), 두 값의 합 1.0 근접성, 결정성 체크

3. 통합 검증(벤치 + warm/cold soak)
- 명령: `python3 scripts/verify_ai.py --benchmark-repeats 1 --warm-cases 60 --cold-cases 20`
- 결과: 모든 단계 통과

## 핵심 수치

- Soak(200) 평균 지연: 66.05ms, p95: 216.08ms, max: 241.19ms
- Warm soak(60) 평균 지연: 59.65ms
- Cold soak(20) 평균 지연: 56.27ms
- 모든 검증에서 Failures: 0

## 해석

- 현재 추천 시스템의 확률 출력은 회귀 케이스와 대량 샘플링 기준 모두에서 일관적으로 유효하다.
- 특히 cover 모드의 성공/실패 확률은 자동 검증에서 범위 및 보완 관계(합≈1)를 지속적으로 만족했다.
- Upper bonus 근접, yacht bonus 활성 등 경계 시나리오가 soak 케이스 믹스에 포함되어 있으며 오류가 보고되지 않았다.

## 다음 권장

- 릴리즈 전에는 `scripts/verify_ai.py`를 CI 필수 단계로 고정.
- 주기적으로 `--cases`를 늘린 soak(예: 1000) 실행해 장기 안정성 추적.
