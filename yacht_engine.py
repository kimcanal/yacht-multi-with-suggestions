import itertools
from collections import Counter

CATS = {
    'Ones': 0, 'Twos': 1, 'Threes': 2, 'Fours': 3, 'Fives': 4, 'Sixes': 5,
    'Choice': 6, '4 of a Kind': 7, 'Full House': 8, 'Single Straight': 9, 'Large Straight': 10, 'Yacht': 11
}

OUTCOMES_CACHE = {}
EPS = 1e-12

def get_outcomes_probs(k):
    if k in OUTCOMES_CACHE: return OUTCOMES_CACHE[k]
    counts = Counter()
    for out in itertools.product(range(1, 7), repeat=k):
        counts[tuple(sorted(out))] += 1
    total = 6**k
    probs = [(list(out), cnt / total) for out, cnt in counts.items()]
    OUTCOMES_CACHE[k] = probs
    return probs

# --- 점수 계산 최적화 (Pre-calculation) ---
def _calc_score_internal(dice, category_idx):
    counts = Counter(dice)
    
    if 0 <= category_idx <= 5: # 1~6
        return counts[category_idx + 1] * (category_idx + 1)
    
    if category_idx == CATS['Choice']:
        return sum(dice)

    if category_idx == CATS['4 of a Kind']:
        # 4개 이상 동일하면 5개 전체 합산
        most_common = counts.most_common(1)[0]
        if most_common[1] >= 4:
            return sum(dice)
        return 0
    
    if category_idx == CATS['Full House']:
        # 5개 전체 합산 (3+2 조합일 때만)
        if len(counts) == 2 and 3 in counts.values() and 2 in counts.values():
            return sum(dice)
        # 5 of a kind도 Full House로 인정
        if len(counts) == 1 and len(dice) == 5:
            return sum(dice)
        return 0
    
    if category_idx == CATS['Single Straight']:
        # 연속 4개: 1-2-3-4, 2-3-4-5, 3-4-5-6 중 하나, 15점 고정
        s_dice = set(dice)
        straights = [{1,2,3,4}, {2,3,4,5}, {3,4,5,6}]
        if any(s.issubset(s_dice) for s in straights):
            return 15
        return 0
        
    if category_idx == CATS['Large Straight']:
        # 연속 5개: 1-2-3-4-5 또는 2-3-4-5-6, 30점 고정
        s_dice = set(dice)
        if {1,2,3,4,5}.issubset(s_dice) or {2,3,4,5,6}.issubset(s_dice):
            return 30
        return 0

    if category_idx == CATS['Yacht']:
        if len(counts) == 1: return 50
        return 0
        
    return 0

SCORE_TABLE = {}
# 모든 주사위 조합(252가지)에 대한 점수를 미리 계산하여 캐싱
for d in itertools.combinations_with_replacement(range(1, 7), 5):
    SCORE_TABLE[d] = {}
    for cat_idx in CATS.values():
        SCORE_TABLE[d][cat_idx] = _calc_score_internal(d, cat_idx)

def calc_score(dice, category_idx):
    return SCORE_TABLE[tuple(sorted(dice))][category_idx]

def get_success_probability(kept_dice, category_idx):
    num_reroll = 5 - len(kept_dice)
    if num_reroll == 0:
        return 1.0 if calc_score(kept_dice, category_idx) > 0 else 0.0
    
    success_prob = 0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        if calc_score(next_dice, category_idx) > 0:
            success_prob += prob
    return success_prob

def get_category_expected_value(kept_dice, category_idx, num_reroll):
    """특정 카테고리에 대한 기대값 계산"""
    if num_reroll == 0:
        return float(calc_score(kept_dice, category_idx))
    
    ev = 0
    for outcome, prob in get_outcomes_probs(num_reroll):
        next_dice = kept_dice + outcome
        score = calc_score(next_dice, category_idx)
        ev += prob * score
    return ev

def _find_4kind_keeps(dice):
    """4 of a Kind를 keep할 수 있는 경우 찾기: 4개 이상 또는 3개"""
    from collections import Counter
    counts = Counter(dice)
    
    candidates = []
    
    # 경우 1: 같은 눈 4개 이상
    for val in range(6, 0, -1):
        if counts[val] >= 4:
            candidates.append({'keep_val': val, 'keep_count': 4, 'prob_base': 1.0})
            break
    
    # 경우 2: 같은 눈 3개 있는 경우 - 가장 큰 값부터
    if not candidates:
        for val in range(6, 0, -1):
            if counts[val] >= 3:
                candidates.append({'keep_val': val, 'keep_count': 3, 'prob_base': 0.33})
                break
    
    return candidates

def solve_best_move(dice, rolls_left, open_categories):
    # 1. 기본 EV 계산 (점수형 카테고리나 족보 실패 시를 대비한 베이스라인)
    best_ev = -1
    best_keep_indices = []

    for i in range(32):
        keep_indices = []
        kept_dice = []
        for j in range(5):
            if (i >> j) & 1:
                keep_indices.append(j)
                kept_dice.append(dice[j])
        
        num_reroll = 5 - len(kept_dice)
        
        if num_reroll == 0:
            current_score = 0
            for cat in open_categories:
                current_score = max(current_score, calc_score(kept_dice, cat))
            ev = current_score
        else:
            ev = 0
            for outcome, prob in get_outcomes_probs(num_reroll):
                next_dice = kept_dice + outcome
                max_s = 0
                for cat in open_categories:
                    max_s = max(max_s, calc_score(next_dice, cat))
                ev += prob * max_s
        
        if ev > best_ev:
            best_ev = ev
            best_keep_indices = keep_indices

    # 2. 주요 족보별 최대 확률 Keep 찾기 (3-Kind 제거됨)
    hand_cats = ['Yacht', '4 of a Kind', 'Full House', 'Large Straight', 'Single Straight']
    # 우선순위(동률 시 점수가 높은 순)
    hand_priority = {'Yacht': 5, 'Large Straight': 4, 'Full House': 3, '4 of a Kind': 2, 'Single Straight': 1}
    
    best_hand_moves = []
    
    for cat_name in hand_cats:
        cat_idx = CATS[cat_name]
        if cat_idx not in open_categories: continue
        
        # 4 of a Kind는 별도 로직
        if cat_name == '4 of a Kind':
            kind_candidates = _find_4kind_keeps(dice)
            if kind_candidates:
                for cand in kind_candidates:
                    val = cand['keep_val']
                    keep_count = cand['keep_count']
                    prob_base = cand['prob_base']
                    # 성공 시 기대값: 5개 전체 합 (4개 동일 + 나머지 1개 평균 3.5)
                    if keep_count >= 4:
                        conditional_ev = sum(dice)
                    else:
                        conditional_ev = val * 4 + 3.5
                    
                    best_hand_moves.append({
                        'name': cat_name,
                        'prob': prob_base,
                        'keep_indices': [],  # 실제 인덱스는 나중에 매칭
                        'priority': hand_priority[cat_name],
                        'tie_values': [val],
                        'tie_keeps': [],
                        'conditional_ev': conditional_ev,
                        'kind_val': val,
                        'kind_count': keep_count
                    })
                continue
            # kind_candidates가 없으면 일반 확률 탐색으로 진행

        # 4 of a Kind 후보가 없으면, 모든 keep 조합에서 최대 확률 찾기 (일반 로직)
        max_prob = -1.0
        best_k = []
        best_k_values = []
        tie_sensitive = cat_name in ('Full House', 'Single Straight', 'Large Straight')
        tie_candidates = []
        
        for i in range(32):
            keep_indices = []
            kept_dice = []
            for j in range(5):
                if (i >> j) & 1:
                    keep_indices.append(j)
                    kept_dice.append(dice[j])
            
            prob = get_success_probability(kept_dice, cat_idx)
            tie_values = sorted([dice[idx] for idx in keep_indices], reverse=True)
            if prob > max_prob + EPS:
                max_prob = prob
                best_k = keep_indices
                best_k_values = tie_values
                tie_candidates = [{'keep_indices': keep_indices, 'values': tie_values}]
            elif abs(prob - max_prob) <= EPS and prob > 0:
                tie_candidates.append({'keep_indices': keep_indices, 'values': tie_values})
                # 확률이 같으면 더 큰 눈 조합을 우선
                if tie_values > best_k_values:
                    best_k = keep_indices
                    best_k_values = tie_values
        
        # Full House는 모든 눈이 다르면 굳이 일부를 남기지 말고 전부 굴리는 선택을 우선
        if cat_name == 'Full House' and max_prob > 0:
            empty_keep = next((c for c in tie_candidates if not c['keep_indices']), None)
            if empty_keep:
                best_k = []
                best_k_values = []
                tie_candidates = [empty_keep] + [c for c in tie_candidates if c is not empty_keep]

        if max_prob > 0:
            # 4 of a Kind 일반 탐색 후 결과 (kind_candidates 없는 경우)
            best_hand_moves.append({
                'name': cat_name,
                'prob': max_prob,
                'keep_indices': best_k,
                'priority': hand_priority[cat_name],
                'tie_values': best_k_values,
                'tie_keeps': sorted(tie_candidates, key=lambda t: t['values'], reverse=True),
                'conditional_ev': sum(best_k) + 3.5 * (5 - len(best_k)) if cat_name == '4 of a Kind' else 0
            })
        continue
        
        # 다른 족보들 (Yacht, Full House, Straights)
        max_prob = -1.0
        best_k = []
        best_k_values = []
        tie_sensitive = cat_name in ('Full House', 'Single Straight', 'Large Straight')
        tie_candidates = []

        for i in range(32):
            keep_indices = []
            kept_dice = []
            for j in range(5):
                if (i >> j) & 1:
                    keep_indices.append(j)
                    kept_dice.append(dice[j])
            
            prob = get_success_probability(kept_dice, cat_idx)
            tie_values = sorted([dice[idx] for idx in keep_indices], reverse=True)
            if prob > max_prob + EPS:
                max_prob = prob
                best_k = keep_indices
                best_k_values = tie_values
                tie_candidates = [{'keep_indices': keep_indices, 'values': tie_values}]
            elif abs(prob - max_prob) <= EPS:
                tie_candidates.append({'keep_indices': keep_indices, 'values': tie_values})
                if tie_sensitive:
                    if cat_name in ('Single Straight', 'Large Straight'):
                        if (len(keep_indices) < len(best_k)) or (
                            len(keep_indices) == len(best_k) and tie_values > best_k_values
                        ):
                            best_k = keep_indices
                            best_k_values = tie_values
                    else:  # Full House
                        if tie_values > best_k_values:
                            best_k = keep_indices
                            best_k_values = tie_values
        
        if max_prob > 0:
            if tie_sensitive and cat_name in ('Single Straight', 'Large Straight'):
                # Straight류: 같은 확률 중 가장 짧은 길이 선택
                min_len = min(len(c['keep_indices']) for c in tie_candidates)
                shortest_candidates = [c for c in tie_candidates if len(c['keep_indices']) == min_len]
                # 같은 길이 내에서 더 큰 눈 조합 선택
                best_candidate = max(shortest_candidates, key=lambda c: c['values'])
                best_hand_moves.append({
                    'name': cat_name,
                    'prob': max_prob,
                    'keep_indices': best_candidate['keep_indices'],
                    'priority': hand_priority[cat_name],
                    'tie_values': best_candidate['values'],
                    'tie_keeps': sorted(tie_candidates, key=lambda t: t['values'], reverse=True)
                })
            else:
                best_hand_moves.append({
                    'name': cat_name,
                    'prob': max_prob,
                    'keep_indices': best_k,
                    'priority': hand_priority[cat_name],
                    'tie_values': best_k_values,
                    'tie_keeps': sorted(tie_candidates, key=lambda t: t['values'], reverse=True)
                })

    # 3. 추천 결정: 확률이 가장 높은 족보 전략 선택 (확률 같으면 우선순위 높은 순)
    if best_hand_moves:
        # 4 of a Kind는 실제 인덱스 매칭
        for move in best_hand_moves:
            if move['name'] == '4 of a Kind':
                kind_val = move.get('kind_val')
                kind_count = move.get('kind_count')
                if kind_val and kind_count:
                    # 같은 눈 kind_count개만큼의 인덱스를 찾아서 keep_indices 설정
                    indices = [i for i, d in enumerate(dice) if d == kind_val][:kind_count]
                    move['keep_indices'] = indices
                    move['tie_keeps'] = []
        
        # 확률, 우선순위, 그리고 동률 시 더 큰 눈을 선호
        best_hand_moves.sort(key=lambda x: (x['prob'], x['priority'], x.get('tie_values', [])), reverse=True)
        best_strategy = best_hand_moves[0]
        # 선택된 족보 전략의 EV를 계산하여 베이스라인보다 과도하게 낮으면 유지하지 않음
        strategy_keep = best_strategy['keep_indices']
        kept_dice = [dice[i] for i in strategy_keep]
        num_reroll = 5 - len(strategy_keep)
        if num_reroll == 0:
            strat_ev = 0
            for cat in open_categories:
                strat_ev = max(strat_ev, calc_score(kept_dice, cat))
        else:
            strat_ev = 0
            for outcome, prob in get_outcomes_probs(num_reroll):
                next_dice = kept_dice + outcome
                max_s = 0
                for cat in open_categories:
                    max_s = max(max_s, calc_score(next_dice, cat))
                strat_ev += prob * max_s
        # 베이스라인 EV보다 낮으면 기본 EV 유지, 아니면 족보 전략 반영
        if strat_ev >= best_ev:
            best_keep_indices = strategy_keep

    # Breakdown 생성 (dice_recommendations 이전에 먼저 생성)
    breakdown = []
    hand_cats_display = ['4 of a Kind', 'Full House', 'Single Straight', 'Large Straight', 'Yacht']
    
    for cat_name in hand_cats_display:
        cat_idx = CATS[cat_name]
        if cat_idx not in open_categories:
            continue  # 이미 점수를 받은 카테고리는 표시하지 않음

        # best_hand_moves에서 해당 족보 찾기
        same_cat_moves = [m for m in best_hand_moves if m['name'] == cat_name]
        
        if not same_cat_moves:
            # 모두 다른 눈이라 4 of a Kind, Yacht, Full House에 유의미한 keep이 없을 때는 다시 굴리기 제안
            if len(set(dice)) == 5 and cat_name in ('Yacht', '4 of a Kind', 'Full House'):
                keep_str = "Keep 후보 없음: 다시 돌리기"
            else:
                keep_str = "불가능"
            breakdown.append({
                "name": cat_name,
                "prob": 0.0,
                "val_str": "",
                "type": "hand",
                "keep_str": keep_str,
                "keep_indices": []
            })
            continue
        
        move = same_cat_moves[0]
        
        # 확률이 정확히 0이면 불가능으로 표시
        if move['prob'] == 0:
            breakdown.append({
                "name": cat_name,
                "prob": 0.0,
                "val_str": "",
                "type": "hand",
                "keep_str": "불가능",
                "keep_indices": []
            })
            continue
        
        # 4 of a Kind: 여러 후보 표시
        if cat_name == '4 of a Kind':
            if len(same_cat_moves) > 1:
                keep_ev_strs = []
                for m in same_cat_moves:
                    val = m.get('kind_val')
                    count = m.get('kind_count')
                    ev = m.get('conditional_ev', 0)
                    if val and count:
                        keep_ev_strs.append(f"[{', '.join([str(val)] * count)}] → {round(ev, 1)}점")
                keep_str = f"Keep 후보: {', '.join(keep_ev_strs)}"
            else:
                val = move.get('kind_val')
                count = move.get('kind_count')
                if val and count:
                    keep_str = f"[{', '.join([str(val)] * count)}]"
                else:
                    keep_str = f"[{', '.join([str(v) for v in move.get('tie_values', [])])}]"
                score_str = f"완성시 기대값 {round(move.get('conditional_ev', 0), 1)}점"
                keep_str = f"{keep_str} keep → {score_str}"
            
            breakdown.append({
                "name": cat_name,
                "prob": move['prob'],
                "val_str": f"{move['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": keep_str,
                "keep_indices": move['keep_indices']
            })
            continue
        
        # 다른 족보들
        if cat_name == 'Yacht':
            keep_vals = [str(dice[i]) for i in sorted(move['keep_indices'])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
            score_str = "50점 (확정)"
            if "Keep 후보" in keep_str:
                final_keep = keep_str
            elif keep_vals:
                final_keep = f"{keep_str} keep"
            else:
                final_keep = keep_str
            breakdown.append({
                "name": cat_name,
                "prob": move['prob'],
                "val_str": f"{move['prob'] * 100:.2f}%",
                "type": "hand",
                "keep_str": f"{final_keep} → {score_str}",
                "keep_indices": move['keep_indices']
            })
            continue

        tie_keeps = move.get('tie_keeps') or []
        if len(tie_keeps) > 1:
            # Full House: 빈 keep가 있으면 그것만 남기고 나머지는 제거하여 "모두 굴리기"를 우선 노출
            if cat_name == 'Full House':
                empty_only = [c for c in tie_keeps if not c['keep_indices']]
                if empty_only:
                    tie_keeps = empty_only
                else:
                    tie_keeps = [c for c in tie_keeps if c['keep_indices']]
            normalized = []
            for cand in tie_keeps:
                vals = [dice[i] for i in sorted(cand['keep_indices'])]
                norm_vals = tuple(sorted(vals, reverse=True))
                normalized.append((norm_vals, len(vals)))
            uniq = {}
            for norm_vals, vlen in normalized:
                if norm_vals not in uniq:
                    uniq[norm_vals] = vlen

            def sort_key(item):
                vals, vlen = item
                if cat_name in ('Single Straight', 'Large Straight'):
                    return (vlen, vals)
                else:
                    return (-vlen, vals)

            items = sorted(uniq.items(), key=sort_key, reverse=(cat_name not in ('Single Straight', 'Large Straight')))

            if cat_name in ('Single Straight', 'Large Straight'):
                min_len = min(vlen for (_, vlen) in items) if items else 0
                min_items = [(vals, vlen) for (vals, vlen) in items if vlen == min_len]
                min_items.sort(key=lambda x: x[0], reverse=True)
                display = min_items[:1]
                # 선택된 display의 keep_indices를 찾아서 업데이트
                if display:
                    target_vals = set(display[0][0])
                    for cand in tie_keeps:
                        cand_vals = set(dice[i] for i in cand['keep_indices'])
                        if cand_vals == target_vals:
                            move['keep_indices'] = cand['keep_indices']
                            break
            else:
                display = items[:3]

            all_keep_strs = [f"[{', '.join(map(str, vals))}]" for (vals, _) in display]
            if len(all_keep_strs) == 1:
                keep_str = all_keep_strs[0]
            else:
                keep_str = f"Keep 후보: {', '.join(all_keep_strs)}"
        else:
            keep_vals = [str(dice[i]) for i in sorted(move['keep_indices'])]
            keep_str = f"[{', '.join(keep_vals)}]" if keep_vals else "모두 굴리기"
        
        # 족보별 점수
        if cat_name == 'Yacht':
            score_str = "50점 (확정)"
        elif cat_name == 'Large Straight':
            score_str = "30점 (확정)"
        elif cat_name == 'Single Straight':
            score_str = "15점 (확정)"
        elif cat_name == 'Full House':
            score_str = "합계 점수"
        else:
            score_str = "?"
        
        breakdown.append({
            "name": cat_name,
            "prob": move['prob'],
            "val_str": f"{move['prob'] * 100:.2f}%",
            "type": "hand",
            "keep_str": f"{keep_str if 'Keep 후보' in keep_str else (keep_str if keep_str == '모두 굴리기' else keep_str + ' keep')} → {score_str}",
            "keep_indices": move['keep_indices']
        })
    
    # 족보가 모두 불가능하거나, 족보를 모두 채웠을 때 상단부 표시
    hand_rows = [b for b in breakdown if b.get("type") == "hand"]
    hand_cats_idx = [CATS[name] for name in ['4 of a Kind', 'Full House', 'Single Straight', 'Large Straight', 'Yacht']]
    all_hands_filled = all(cat_idx not in open_categories for cat_idx in hand_cats_idx)
    
    if (hand_rows and all(b.get("prob") == 0 for b in hand_rows)) or all_hands_filled:
        upper_cats = [CATS['Ones'], CATS['Twos'], CATS['Threes'], CATS['Fours'], CATS['Fives'], CATS['Sixes']]
        upper_names = ['Ones', 'Twos', 'Threes', 'Fours', 'Fives', 'Sixes']

        for idx, (cat_val, cat_name) in enumerate(zip(upper_cats, upper_names)):
            if cat_val not in open_categories:
                continue  # 이미 점수를 받았으므로 표시 안 함

            target_val = idx + 1  # Ones=1, Twos=2, ...
            current_count = dice.count(target_val)
            reroll_count = 5 - current_count

            if reroll_count == 0:
                prob_get_more = 1.0
            else:
                prob_get_more = 1.0 - ((5.0/6.0) ** reroll_count)

            breakdown.append({
                "name": cat_name,
                "prob": prob_get_more,
                "val_str": f"{prob_get_more * 100:.2f}%",
                "type": "upper",
                "keep_str": f"{target_val}를 적어도 하나 더 뜰 확률",
                "keep_indices": [i for i, d in enumerate(dice) if d == target_val]
            })

    # breakdown에서 확률이 가장 높은 항목(not upper)을 추천
    # 단, keep이 있는 것만 고려 (keep이 없으면 특정 족보를 "노리는" 게 아니므로)
    best_keep_indices = []
    rec_msg = "모두 굴리기"
    
    hand_breakdown = [b for b in breakdown if b.get('type') == 'hand']
    if hand_breakdown:
        # keep이 있는 족보 중에서 확률이 가장 높은 것 선택
        hand_with_keep = [b for b in hand_breakdown if b.get('keep_indices')]
        if hand_with_keep:
            best_hand = max(hand_with_keep, key=lambda x: x.get('prob', 0))
            best_keep_indices = best_hand['keep_indices']
            kept_vals = [str(dice[i]) for i in sorted(best_keep_indices)]
            rec_msg = f"[{', '.join(kept_vals)}] Keep"
            if best_hand.get('name'):
                rec_msg += f" ({best_hand['name']} 노리기)"
        # else: keep이 없으면 그냥 "모두 굴리기" (족보 지목 안 함)

    # 4. 결과 생성
    dice_recommendations = []
    for i in range(5):
        action = "keep" if i in best_keep_indices else "reroll"
        dice_recommendations.append({
            "index": i,
            "value": dice[i],
            "action": action,
            "confidence": 100
        })

    return {
        "keep_indices": best_keep_indices,
        "expected_value": round(best_ev, 2),
        "dice_recommendations": dice_recommendations,
        "message": rec_msg,
        "breakdown": breakdown
    }