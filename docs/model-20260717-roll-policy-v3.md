# model-20260717-roll-policy-v3

## 판정

`model-20260717-roll-policy-v3`는 v2의 최신-solver 독립 검증 실패를 보완하기 위해 현재 focused/cover 전략으로 새 teacher data를 생성해 재학습한 후보 모델이다.

독립 검증 성능과 exact guard 안전성은 v2보다 크게 개선됐다. 하지만 model-only complete-game 결과가 exact보다 유의하게 낮으므로 **단독 활성화는 금지**다. 현재 서버의 모델 비활성 상태는 유지한다. v3는 다음 단계의 opt-in/staging 후보로만 보관한다.

## 학습 설정

| 항목 | 값 |
| --- | --- |
| Runtime artifact | `artifacts/runtime/models/model-20260717-roll-policy-v3.json` |
| Model SHA-256 | `9498743e0f19ce2e0e8fc1aa48236071286ba8404dd2bf3f2c832a6687015c1c` |
| Teacher rows | 32,768 roll-stage states |
| Teacher SHA-256 | `ddf03b6fc1a9326729b0c16a8ddcc871bced60763c8b6821b0ae3b387583367d` |
| Teacher generation | weighted dice, both modes, 0~11 completed turns |
| Teacher seeds | `20260718`, `20260719`, `20260720`, `20260721` (8,192 rows each) |
| Architecture | 41 input features → ReLU 96 → 462 keep-count classes |
| Training | 120 epochs, batch 256, learning rate 0.003, seed `20260722` |
| Best internal epoch | 115 |
| Internal validation accuracy | 94.25% (6,554 rows) |

학습 teacher와 독립 검증셋은 seed와 파일을 분리했다. 검증셋은 2026-07-17에 생성한 4,096개 weighted roll-state 중 4,095개를 사용했다.

## 독립 검증: v2 대비

| 지표 | v2 | v3 |
| --- | ---: | ---: |
| Top-1 accuracy | 81.59% | **94.04%** |
| Top-3 accuracy | 89.08% | **99.51%** |
| Raw 평균 추가 EV 손실 | 1.2111 | **0.1747** |
| Raw p99 추가 EV 손실 | 14.1026 | **5.8803** |
| Raw 최대 추가 EV 손실 | 27.7715 | 27.2892 |

v3는 일반적인 상태의 모방 성능을 회복했지만, 큰 hard case가 완전히 사라지지는 않았다. 이 때문에 raw/model-only는 승인할 수 없다.

두 번째 독립 seed(`20260723`, 4,095 evaluated states, data SHA-256 `c4569d68f3b1cee30b69457324edbf9e5e7d9f95ab1fa716e8832fe7b6bdf143`)에서도 Top-1 94.14%, Top-3 99.37%, raw 평균 추가 EV 손실 0.1755점, 최대 21.9134점이 나왔다. 첫 번째 독립 seed와 거의 같은 결과라 특정 검증셋에만 맞춘 현상은 아닌 것으로 확인했다.

## Runtime guard 검증

Guard는 confidence `0.95` 이상이면서 모델 keep의 pure objective gap이 `0.25` 이하일 때만 모델을 쓴다. 그 외에는 exact solver로 fallback한다.

| 지표 | v3 결과 |
| --- | ---: |
| 평가 표본 | 4,095 |
| 모델 채택 | 2,154 (52.60%) |
| confidence reject | 389 |
| gap-guard reject | 1,552 |
| 채택 구간 Top-1 | 98.70% |
| fallback 포함 평균 추가 EV 손실 | 0.000031점 |
| fallback 포함 최대 추가 EV 손실 | 0.125091점 |
| 0.25점 초과 | 0건 |

따라서 guard를 유지하는 한 이 독립 표본에서는 큰 품질 손실 없이 v2보다 높은 52.60% 채택률을 얻는다. 단, 이 guard는 exact 계산을 일부 수행하므로 "ML만으로 즉시 응답"과는 다르다.

두 번째 독립 seed의 guard 결과도 채택률 51.97%(2,128 / 4,095), 채택 정확도 98.45%, fallback 포함 평균·최대 추가 EV 손실 모두 0점이었다. 두 독립 seed에서 guard 기준을 통과했다.

## Complete-game paired simulation

Focused mode, 100 games, seed `20260717`; score stage는 동일한 exact 추천을 사용하고 roll policy만 바꿨다.

| Policy | 평균 총점 | exact 대비 | paired 95% CI | 승/동/패 |
| --- | ---: | ---: | ---: | ---: |
| exact | 175.70 | 기준 | - | - |
| v3 runtime guard | 178.32 | +2.62 | -0.70~+5.94 | 18/71/11 |
| v3 model-only | 163.52 | **-12.18** | **-20.21~-4.15** | 35/2/63 |

runtime guard는 exact보다 좋다고 증명되지는 않았지만, 이 표본에서 유의한 악화도 보이지 않았다. model-only의 성능 저하는 유의하므로 단독 모델 배포는 금지한다.

## Indicative latency check

동일 프로세스, cold-cache 대표 6개 시나리오에서 model-only 예측은 약 0.11~0.22 ms였다. 그러나 안전한 runtime guard는 exact gap을 재계산하므로 약 0.21~79.18 ms였고, exact 전체 탐색의 약 58.63~178.75 ms보다 일부 시나리오에서만 빨랐다. 이 수치는 로컬 마이크로벤치마크이므로 production latency 이득의 근거로는 부족하다.

## 다음 배포 기준

1. 별도 staging 인스턴스를 만들고 `YACHT_AI_POLICY_MODEL`을 v3로 설정한다.
2. exact 대비 p95 latency, fallback 비율, 오류율을 기록한다.
3. model-only를 허용하지 않고 `YACHT_AI_POLICY_MIN_CONFIDENCE=0.95`와 objective-gap `0.25`를 고정한다.
4. staging 결과가 품질 열화 없이 충분한 latency 이득을 보일 때만 production opt-in을 검토한다.

## 재현 명령

생성 데이터와 상세 JSON은 `artifacts/generated/`에 있으며 Git에는 포함하지 않는다.

```bash
.venv/bin/python scripts/train_roll_policy.py \
  --data artifacts/generated/model-v3-training/teacher-roll-current-32768.jsonl \
  --output artifacts/runtime/models/model-20260717-roll-policy-v3.json \
  --epochs 120 --hidden-dim 96 --batch-size 256 --learning-rate 0.003 \
  --seed 20260722 --model-id model-20260717-roll-policy-v3 \
  --created-date 2026-07-17

.venv/bin/python scripts/eval_roll_policy_runtime.py \
  --data artifacts/generated/model-validation-20260717/teacher-independent-4096.jsonl \
  --model artifacts/runtime/models/model-20260717-roll-policy-v3.json \
  --val-ratio 1.0 --seed 20260717 \
  --min-confidence 0.95 --guard-gap 0.25
```
