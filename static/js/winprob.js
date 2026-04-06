/**
 * static/js/winprob.js
 * 판세 흐름 추정 및 그래프 렌더링
 */

const CATEGORY_BASELINES = [2.1, 4.2, 6.3, 8.4, 10.5, 12.6, 18.4, 12.7, 18.9, 8.1, 6.7, 3.4];

function estimateProjectedTotal(card, dice = null, rollsLeft = 3) {
    const normalized = Array.isArray(card) ? card.slice(0, 12) : Array(12).fill(null);
    let total = calcTotals(normalized).total;
    const open = [];
    normalized.forEach((value, index) => {
        if (value === null || value === undefined) open.push(index);
    });
    total += open.reduce((sum, index) => sum + CATEGORY_BASELINES[index], 0);

    if (Array.isArray(dice) && dice.length === 5 && rollsLeft < 3 && open.length) {
        const bestLiveScore = open.reduce((best, index) => Math.max(best, calcScore(dice, index)), 0);
        total += bestLiveScore * 0.35;
    }
    return total;
}

function estimateWinChances(myCard, oppCard, options = {}) {
    const myProjected = estimateProjectedTotal(myCard, options.myDice, options.myRollsLeft);
    const oppProjected = estimateProjectedTotal(oppCard, options.oppDice, options.oppRollsLeft);
    const diff = myProjected - oppProjected;
    const myProb = 1 / (1 + Math.exp(-diff / 9));
    return {
        myProbability: myProb,
        oppProbability: 1 - myProb,
        myProjected,
        oppProjected,
        diff,
    };
}

function recordWinChance(history, nextProb) {
    const point = Math.max(0.03, Math.min(0.97, nextProb));
    if (!Array.isArray(history)) return [point];
    const prev = history[history.length - 1];
    if (typeof prev === 'number' && Math.abs(prev - point) < 0.003) return history;
    const updated = history.concat(point);
    return updated.length > 28 ? updated.slice(updated.length - 28) : updated;
}

function renderWinChancePanel(targetId, snapshot, options = {}) {
    const root = document.getElementById(targetId);
    if (!root || !snapshot) return;
    const history = Array.isArray(options.history) ? options.history : [];
    const leftLabel = escapeHtml(options.leftLabel || '나');
    const rightLabel = escapeHtml(options.rightLabel || '상대');
    const myPct = Math.round(snapshot.myProbability * 100);
    const oppPct = 100 - myPct;

    let graph = '';
    if (history.length >= 2) {
        const width = 260;
        const height = 96;
        const step = history.length > 1 ? width / (history.length - 1) : width;
        const points = history.map((value, index) => {
            const x = (index * step).toFixed(1);
            const y = ((1 - value) * (height - 12) + 6).toFixed(1);
            return `${x},${y}`;
        }).join(' ');
        graph = `
            <svg viewBox="0 0 ${width} ${height}" class="winprob-graph" preserveAspectRatio="none">
                <line x1="0" y1="${height / 2}" x2="${width}" y2="${height / 2}" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"></line>
                <polyline fill="none" stroke="#59f0c2" stroke-width="3" points="${points}"></polyline>
            </svg>
        `;
    }

    root.innerHTML = `
        <div class="winprob-head">
            <div class="winprob-title">판세 흐름</div>
            <div class="winprob-sub">현재 점수표와 남은 칸을 바탕으로 흐름을 추정합니다</div>
        </div>
        <div class="winprob-bar">
            <div class="winprob-left" style="width:${myPct}%">${leftLabel} ${myPct}%</div>
            <div class="winprob-right" style="width:${oppPct}%">${rightLabel} ${oppPct}%</div>
        </div>
        <div class="winprob-meta">${leftLabel} 예상 총점 ${snapshot.myProjected.toFixed(1)} / ${rightLabel} 예상 총점 ${snapshot.oppProjected.toFixed(1)}</div>
        ${graph}
    `;
}
