/**
 * static/js/yacht_game.js
 * Yacht 게임의 공통 로직 및 유틸리티 함수
 */

const GameState = (() => {
    let state = {
        dice: [1,1,1,1,1],
        kept: [0,0,0,0,0],
        rollsLeft: 3,
        myCard: Array(12).fill(null),
        oppCard: Array(12).fill(null),
        gameOver: false,
        aiRec: null
    };
    
    return {
        getDice: () => [...state.dice],
        setDice: (value) => { state.dice = [...value]; },
        getKept: () => [...state.kept],
        setKept: (value) => { state.kept = [...value]; },
        getRollsLeft: () => state.rollsLeft,
        setRollsLeft: (value) => { state.rollsLeft = value; },
        getMyCard: () => [...state.myCard],
        setMyCard: (value) => { state.myCard = [...value]; },
        getOppCard: () => [...state.oppCard],
        setOppCard: (value) => { state.oppCard = [...value]; },
        isGameOver: () => state.gameOver,
        setGameOver: (value) => { state.gameOver = value; },
        getAiRec: () => state.aiRec,
        setAiRec: (value) => { state.aiRec = value; },
        getState: () => ({ ...state }),
        setState: (newState) => { state = { ...state, ...newState }; }
    };
})();

const CATS = ['Ones','Twos','Threes','Fours','Fives','Sixes','Choice','4 of a Kind','Full House','Small Straight','Large Straight','Yacht'];

const CAT_DESC = {
    'Ones': '1이 나온 주사위 눈의 총합 \n(최대 5점)',
    'Twos': '2가 나온 주사위 눈의 총합 \n(최대 10점)',
    'Threes': '3이 나온 주사위 눈의 총합 \n(최대 15점)',
    'Fours': '4가 나온 주사위 눈의 총합 \n(최대 20점)',
    'Fives': '5가 나온 주사위 눈의 총합 \n(최대 25점)',
    'Sixes': '6이 나온 주사위 눈의 총합 \n(최대 30점)',
    'Choice': '주사위 눈 5개의 총합 (최대 30점)',
    '4 of a Kind': '동일한 주사위 눈이 4개 이상\n → 주사위 5개의 총합 \n(최대 30점)',
    'Full House': '같은 숫자 3개 + 같은 숫자 2개\n → 주사위 5개의 총합 \n(예: ⚄⚄ + ⚅⚅⚅ = 28점)',
    'Small Straight': '연속된 주사위 눈 4개 이상\n → 고정 15점 \n(예: 1-2-3-4, 2-3-4-5, 3-4-5-6)',
    'Large Straight': '연속된 주사위 눈 5개\n → 고정 30점 \n(1-2-3-4-5 또는 2-3-4-5-6)',
    'Yacht': '동일한 주사위 눈 5개 → 고정 50점\n\n🏆 Yacht Bonus: 이미 Yacht 50점을 받은 후 다시 Yacht를 굴리면,\n다른 칸에 0이 아닌 점수를 기록할 때 추가로 +100점을 받습니다!'
};

const CAT_DICE = {
    'Ones': '⚀⚀⚀⚄⚅ = 3점',
    'Twos': '⚁⚁⚁⚄⚅ = 6점',
    'Threes': '⚂⚂⚂⚄⚅ = 9점',
    'Fours': '⚀⚁⚃⚃⚃ = 12점',
    'Fives': '⚀⚁⚄⚄⚄ = 15점',
    'Sixes': '⚀⚁⚅⚅⚅ = 18점',
    'Choice': '⚂⚃⚄⚅⚅ = 24점',
    '4 of a Kind': '⚄⚅⚅⚅⚅ = 29점',
    'Full House': '⚄⚄⚅⚅⚅ = 28점',
    'Small Straight': '⚀⚁⚂⚃⚄ = 15점',
    'Large Straight': '⚁⚂⚃⚄⚅ = 30점',
    'Yacht': '⚀⚀⚀⚀⚀ = 50점'
};

function playTurnToastSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;
        const env = ctx.createGain();
        env.gain.setValueAtTime(0.14, now);
        env.gain.exponentialRampToValueAtTime(0.001, now + 0.6);

        const osc1 = ctx.createOscillator();
        osc1.type = 'triangle';
        osc1.frequency.setValueAtTime(660, now);
        osc1.frequency.exponentialRampToValueAtTime(990, now + 0.25);

        const osc2 = ctx.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(1320, now + 0.05);
        osc2.frequency.exponentialRampToValueAtTime(1760, now + 0.35);

        osc1.connect(env);
        osc2.connect(env);
        env.connect(ctx.destination);

        osc1.start(now);
        osc2.start(now + 0.05);
        osc1.stop(now + 0.6);
        osc2.stop(now + 0.6);
    } catch (e) {
        console.warn('toast sound failed', e);
    }
}

function playKeepSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
        
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.2);
    } catch (e) {}
}

function calcScore(d, i) {
    const c = {};
    d.forEach(x => c[x] = (c[x] || 0) + 1);
    if (i < 6) return (c[i+1] || 0) * (i+1);
    if (i === 6) return d.reduce((a, b) => a + b); // Choice
    if (i === 7) { // 4 of a Kind
        const mc = Object.entries(c).find(([k, v]) => v >= 4);
        return mc ? d.reduce((a, b) => a + b) : 0;
    }
    if (i === 8) { // Full House
        const v = Object.values(c).sort();
        if (v.length === 1) return d.reduce((a, b) => a + b); // 5 of a kind
        if (v.length === 2 && v[0] === 2 && v[1] === 3) return d.reduce((a, b) => a + b);
        return 0;
    }
    if (i === 9) { // Small Straight
        const u = [...new Set(d)].sort((a,b) => a-b);
        const straights = [[1,2,3,4], [2,3,4,5], [3,4,5,6]];
        return straights.some(s => s.every(x => u.includes(x))) ? 15 : 0;
    }
    if (i === 10) { // Large Straight
        const u = [...new Set(d)].sort((a,b) => a-b);
        return ([1,2,3,4,5].every(x => u.includes(x)) || [2,3,4,5,6].every(x => u.includes(x))) ? 30 : 0;
    }
    if (i === 11) return Object.values(c).includes(5) ? 50 : 0; // Yacht
    return 0;
}

function calcTotals(card) {
    const upper = card.slice(0, 6).reduce((a, v) => a + (v || 0), 0);
    const bonus = upper >= 63 ? 35 : 0;
    const lower = card.slice(6).reduce((a, v) => a + (v || 0), 0);
    return { upper, bonus, total: upper + bonus + lower };
}

function renderDice() {
    const dotMap = {
        1: [5], 2: [1,9], 3: [1,5,9], 4: [1,3,7,9], 5: [1,3,5,7,9], 6: [1,3,4,6,7,9]
    };

    const g = document.getElementById('dice-grid');
    g.innerHTML = CATS.slice(0,5).map((_, i) => `
        <div class="dice-item" id="dice-item-${i}">
            <div class="die-container" id="die-container-${i}">
                <div class="die" id="die-${i}">
                    ${[1,2,3,4,5,6].map(f => `
                        <div class="die-face face-${f}">
                            ${[1,2,3,4,5,6,7,8,9].map(d => 
                                `<div class="dot ${dotMap[f].includes(d) ? '' : 'hidden'}"></div>`
                            ).join('')}
                        </div>
                    `).join('')}
                </div>
            </div>
            <button class="keep-btn" id="keep-${i}" onclick="toggleLock(${i})">
                <span id="keep-text-${i}">KEEP</span>
            </button>
            <div class="lock-label" id="lock-${i}"></div>
        </div>
    `).join('');
    
    const aiInfoTip = document.getElementById('ai-info-tip');
    if (aiInfoTip) {
        // isMultiplayer 변수는 각 HTML 파일에서 정의됨
        aiInfoTip.style.display = (typeof isMultiplayer !== 'undefined' && isMultiplayer) ? 'none' : 'block';
    }
    
    updateDice();
}

function renderCard(card, isMine, title) {
    const totals = calcTotals(card);
    let h = '';
    CATS.forEach((c, i) => {
        if (i === 6) {
            h += `<div class="score-item subtotal" style="background:rgba(255,255,255,0.1); cursor:default;" data-desc="상단 항목의 점수 합계.\n목표는 63점 (각 숫자 3개씩)" data-dice="" onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"><span class="score-name">Subtotal (1-6)</span><span class="score-val">${totals.upper}/63</span></div>`;
            h += `<div class="score-item bonus" data-desc="상단 합계 63점 이상 \n→ 보너스 35점" data-dice="" onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"><span class="score-name">Upper Bonus</span><span class="score-val">+${totals.bonus}</span></div>`;
        }
        const clickable = isMine && !gameOver && isMyTurn() && card[i] === null && rollsLeft < 3;
        const showPreview = !gameOver && card[i] === null && rollsLeft < 3 && ((isMine && isMyTurn()) || (!isMine && !isMyTurn()));
        const sc = calcScore(dice, i);
        const p = showPreview ? `<span class="score-preview">(${sc})</span>` : '';
        const classes = `score-item ${card[i] !== null ? 'filled' : ''} ${!isMine ? 'disabled' : ''}`;
        const desc = CAT_DESC[c] || '';
        const diceEx = '예시) ' + CAT_DICE[c] || '';
        const handlers = clickable
            ? `onclick="pickCategory(${i})" onmouseenter="showTip(this); previewScore(${i})" onmouseleave="hideTip(this); clearPreview()" ontouchstart="showTip(this); previewScore(${i})" ontouchend="hideTip(this); clearPreview()"`
            : `onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"`;
        h += `<div class="${classes}" ${handlers} data-desc="${desc}" data-dice="${diceEx}"><span class="score-name">${c}</span><span class="score-val">${card[i] !== null ? card[i] : '-'}${p}</span><div class="custom-tip" style="display:none;"></div></div>`;
    });
    h += `<div class="total-score"><span>TOTAL</span><span>${totals.total}</span></div>`;
    
    const isCurrentTurn = (typeof isMultiplayer !== 'undefined' && isMultiplayer) ? (isMine ? isMyTurn() : !isMyTurn()) : isMine;
    const titleStyle = isCurrentTurn ? 'color: #00ff00; text-shadow: 0 0 20px rgba(0, 255, 0, 0.8); font-weight: bold;' : 'color: #00ffcc;';
    
    return `<div class="scorecard-title" style="${titleStyle}">${title}</div><div>${h}</div>`;
}

function showTip(el) {
    // 각 항목 위에 말풍선(div)로 표시
    hideTip(el);
    const desc = el.getAttribute('data-desc') || '';
    const dice = el.getAttribute('data-dice') || '';
    if (!desc && !dice) return;
    const tip = el.querySelector('.custom-tip');
    if (tip) {
        tip.style.display = 'flex';
        tip.style.flexDirection = 'column';
        tip.style.alignItems = 'flex-start';
        tip.innerHTML = `<div class="tip-dice" style="font-weight:bold; color:#00ffd0; font-size:1.08em; margin-bottom:2px;">${dice}</div><div class="tip-desc" style="font-size:1.04em; line-height:1.6; color:#fff;">${desc}</div>`;
        tip.style.position = 'absolute';
        tip.style.left = '60%';
        //tip.style.top = '-64px';
        const rect = el.getBoundingClientRect();
        const tipHeight = 80; // 대략적인 툴팁 높이 예상값

        // 요소가 화면 위쪽에 너무 붙어있으면(80px 미만), 툴팁을 요소 아래로 내립니다.
        if (rect.top < tipHeight) {
            tip.style.top = '100%'; // 요소 바로 아래
            tip.style.marginTop = '10px'; // 약간의 간격
            // 화살표 방향도 바꾸면 좋겠지만, JS 스타일로는 복잡하니 위치만 조정해도 충분합니다.
        } else {
            tip.style.top = '-64px'; // 기존 위치 유지
            tip.style.marginTop = '0';
        }
        tip.style.transform = 'translateX(-50%)';
        tip.style.background = 'linear-gradient(135deg, #23234a 80%, #1a1a2e 100%)';
        tip.style.opacity = '0.97';
        tip.style.color = '#fff';
        tip.style.padding = '13px 20px 12px 20px';
        tip.style.borderRadius = '13px';
        tip.style.fontSize = '1em';
        tip.style.boxShadow = '0 6px 32px 0 rgba(0,0,0,0.28), 0 1.5px 0 #00ffd0 inset';
        tip.style.zIndex = '1500';
        tip.style.whiteSpace = 'pre-line';
        tip.style.pointerEvents = 'none';
        tip.style.minWidth = '180px';
        tip.style.maxWidth = '320px';
        tip.style.width = 'max-content';
        tip.style.height = 'auto';
        tip.style.textAlign = 'left';
        tip.style.fontFamily = 'inherit';
        tip.style.overflowWrap = 'break-word';
        tip.style.wordBreak = 'keep-all';
        tip.style.border = '1.5px solid #00ffd0';
        tip.style.overflow = 'visible';
        tip.style.boxSizing = 'border-box';
        // 모바일/좁은 화면 대응
        if (window.innerWidth < 600) {
            tip.style.fontSize = '0.98em';
            tip.style.padding = '9px 8px 8px 8px';
            tip.style.minWidth = '120px';
            tip.style.maxWidth = '90vw';
            tip.style.width = 'auto';
            tip.style.top = '-54px';
        }
    }
}

function hideTip(el) {
    // 말풍선 숨김
    const tip = el.querySelector('.custom-tip');
    if (tip) tip.style.display = 'none';
}

function previewScore(i) {
    if (myCard[i] !== null || rollsLeft === 3 || gameOver) return;
    const sc = calcScore(dice, i);
    const curTotals = calcTotals(myCard);
    const temp = [...myCard];
    temp[i] = sc;
    const newTotals = calcTotals(temp);

    // TOTAL 예상점수
    const totalEl = document.querySelector('.scorecard-area .total-score span:last-child');
    if (totalEl) {
        const diff = newTotals.total - curTotals.total;
        totalEl.innerHTML = `${curTotals.total} <span style="color:#00ffcc; font-size:0.8em"> (+${diff}) ➜ ${newTotals.total}</span>`;
    }

    // SUBTOTAL(상단합계) 예상점수
    const subtotalEl = document.querySelector('.score-item.subtotal .score-val');
    if (subtotalEl) {
        const diff = newTotals.upper - curTotals.upper;
        subtotalEl.innerHTML = `${curTotals.upper}/63 <span style="color:#00ffcc; font-size:0.8em"> (+${diff}) ➜ ${newTotals.upper}/63</span>`;
    }

    // 보너스 예상점수
    const bonusEl = document.querySelector('.score-item.bonus .score-val');
    if (bonusEl && newTotals.bonus > curTotals.bonus) {
        bonusEl.innerHTML = `+${curTotals.bonus} <span style="color:#ffd700; font-weight:bold"> (+35) ➜ ${newTotals.bonus}</span>`;
        bonusEl.parentElement.style.background = 'rgba(255, 215, 0, 0.25)';
    }
}

function clearPreview() {
    updateScorecard();
}