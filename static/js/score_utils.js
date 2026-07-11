/**
 * static/js/score_utils.js
 * 점수 계산 및 점수표 렌더링 유틸리티
 */

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
    'Yacht': '동일한 주사위 눈 5개 → 고정 50점\n🏆 이후 Yacht 재발생 시 다른 칸 기록에 +100점 보너스'
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

function calcScore(d, i) {
    const c = {};
    d.forEach(x => c[x] = (c[x] || 0) + 1);
    if (i < 6) return (c[i+1] || 0) * (i+1);
    if (i === 6) return d.reduce((a, b) => a + b);
    if (i === 7) {
        const mc = Object.entries(c).find(([, v]) => v >= 4);
        return mc ? d.reduce((a, b) => a + b) : 0;
    }
    if (i === 8) {
        const v = Object.values(c).sort();
        if (v.length === 1) return d.reduce((a, b) => a + b);
        if (v.length === 2 && v[0] === 2 && v[1] === 3) return d.reduce((a, b) => a + b);
        return 0;
    }
    if (i === 9) {
        const u = [...new Set(d)].sort((a, b) => a - b);
        const straights = [[1,2,3,4], [2,3,4,5], [3,4,5,6]];
        return straights.some((s) => s.every((x) => u.includes(x))) ? 15 : 0;
    }
    if (i === 10) {
        const u = [...new Set(d)].sort((a, b) => a - b);
        return ([1,2,3,4,5].every((x) => u.includes(x)) || [2,3,4,5,6].every((x) => u.includes(x))) ? 30 : 0;
    }
    if (i === 11) return Object.values(c).includes(5) ? 50 : 0;
    return 0;
}

function calcTotals(card) {
    const upper = card.slice(0, 6).reduce((a, v) => a + (v || 0), 0);
    const bonus = upper >= 63 ? 35 : 0;
    const lower = card.slice(6).reduce((a, v) => a + (v || 0), 0);
    return { upper, bonus, total: upper + bonus + lower };
}

function countFilledCategories(card) {
    if (!Array.isArray(card)) return 0;
    return card.slice(0, CATS.length).filter((value) => value !== null && value !== undefined).length;
}

function countOpenCategories(card) {
    return Math.max(0, CATS.length - countFilledCategories(card));
}

function renderScoreMetric(label, value, options = {}) {
    const idAttr = options.id ? ` id="${options.id}"` : '';
    const toneClass = options.tone ? ` ${options.tone}` : '';
    const sub = options.sub ? `<span class="score-overview-sub">${escapeHtml(options.sub)}</span>` : '';
    const meterValue = Number.isFinite(Number(options.meter))
        ? Math.max(0, Math.min(1, Number(options.meter)))
        : null;
    const meter = meterValue === null
        ? ''
        : `<span class="score-overview-meter"><i style="width:${meterValue * 100}%"></i></span>`;
    return `
        <div class="score-overview-card${toneClass}">
            <span class="score-overview-label">${escapeHtml(label)}</span>
            <strong class="score-overview-value"${idAttr}>${value}</strong>
            ${sub}
            ${meter}
        </div>
    `;
}

function formatUpperBonusProgress(totals) {
    return totals.bonus > 0 ? `+${totals.bonus} 확보` : `${Math.max(0, 63 - totals.upper)}점 남음`;
}

function renderSingleScoreOverview(card, totals, options = {}) {
    const openCount = countOpenCategories(card);
    return `
        <div class="score-overview">
            ${renderScoreMetric('TOTAL', totals.total, { id: options.previewIds ? 'summary-total' : '', tone: 'primary' })}
            ${renderScoreMetric('Upper', `${totals.upper}/63`, { id: options.previewIds ? 'summary-subtotal' : '', meter: totals.upper / 63 })}
            ${renderScoreMetric('Upper Bonus', formatUpperBonusProgress(totals), {
                id: options.previewIds ? 'summary-bonus' : '',
                tone: totals.bonus > 0 ? 'bonus' : '',
                sub: totals.bonus > 0 ? '상단 합계 63점 달성' : '상단 합계 63점 달성 시 +35점',
                meter: totals.bonus > 0 ? 1 : totals.upper / 63,
            })}
            ${renderScoreMetric('Open', openCount, { sub: '남은 칸', meter: countFilledCategories(card) / CATS.length })}
        </div>
    `;
}

function formatScoreDiff(leftTotal, rightTotal) {
    const diff = leftTotal - rightTotal;
    if (diff === 0) return '동점';
    return diff > 0 ? `+${diff}` : `${diff}`;
}

function renderCompareOverview(leftCard, rightCard, leftTotals, rightTotals, options = {}) {
    const diff = leftTotals.total - rightTotals.total;
    const diffTone = diff > 0 ? 'good' : diff < 0 ? 'risk' : '';
    return `
        <div class="score-duel-overview">
            ${renderScoreMetric(options.leftShortLabel || '나', leftTotals.total, { id: options.previewIds ? 'summary-total' : '', tone: 'primary' })}
            ${renderScoreMetric(options.rightShortLabel || '상대', rightTotals.total)}
            ${renderScoreMetric('차이', formatScoreDiff(leftTotals.total, rightTotals.total), { tone: diffTone })}
            ${renderScoreMetric('Upper', `${leftTotals.upper}/63`, { id: options.previewIds ? 'summary-subtotal' : '', sub: rightTotals.upper ? `상대 ${rightTotals.upper}/63` : '', meter: leftTotals.upper / 63 })}
            ${renderScoreMetric('Upper Bonus', formatUpperBonusProgress(leftTotals), {
                id: options.previewIds ? 'summary-bonus' : '',
                tone: leftTotals.bonus > 0 ? 'bonus' : '',
                sub: `63점 달성 시 +35점 · 상대 ${formatUpperBonusProgress(rightTotals)}`,
                meter: leftTotals.bonus > 0 ? 1 : leftTotals.upper / 63,
            })}
        </div>
    `;
}

function buildTurnProgress(filledTurns, totalTurns, options = {}) {
    const safeTotal = Math.max(1, Number(totalTurns) || CATS.length);
    const safeFilled = Math.max(0, Math.min(safeTotal, Number(filledTurns) || 0));
    const started = options.started !== undefined ? Boolean(options.started) : true;
    const gameOver = Boolean(options.gameOver);

    let current = 0;
    if (gameOver) {
        current = safeFilled;
    } else if (!started && safeFilled === 0) {
        current = 0;
    } else {
        current = Math.min(safeTotal, safeFilled + 1);
    }

    return {
        current,
        total: safeTotal,
        filled: safeFilled,
        started,
        gameOver,
        label: `${current}/${safeTotal}`,
    };
}

function getSingleTurnProgress(card, gameOver = false) {
    return buildTurnProgress(countFilledCategories(card), CATS.length, {
        started: true,
        gameOver,
    });
}

function getMultiTurnProgress(myCard, oppCard, options = {}) {
    return buildTurnProgress(
        countFilledCategories(myCard) + countFilledCategories(oppCard),
        CATS.length * 2,
        options
    );
}

function renderCard(card, isMine, title) {
    const totals = calcTotals(card);
    let h = '';
    CATS.forEach((c, i) => {
        const clickable = isMine && !gameOver && isMyTurn() && card[i] === null && rollsLeft < 3;
        const showPreview = !gameOver && card[i] === null && rollsLeft < 3 && ((isMine && isMyTurn()) || (!isMine && !isMyTurn()));
        const sc = calcScore(dice, i);
        const p = showPreview ? `<span class="score-preview">(${sc})</span>` : '';
        const classes = `score-item ${card[i] !== null ? 'filled' : ''} ${!isMine ? 'disabled' : ''}`;
        const desc = CAT_DESC[c] || '';
        const diceEx = '예시) ' + CAT_DICE[c] || '';
        const tipLayoutAttr = clickable ? 'data-tip-layout="score-preview"' : '';
        const handlers = clickable
            ? `onclick="pickCategory(${i})" onmouseenter="showTip(this); previewScore(${i})" onmouseleave="hideTip(this); clearPreview()" ontouchstart="showTip(this); previewScore(${i})" ontouchend="hideTip(this); clearPreview()"`
            : `onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"`;
        h += `<div class="${classes}" ${handlers} ${tipLayoutAttr} data-desc="${desc}" data-dice="${diceEx}"><span class="score-name">${c}</span><span class="score-val">${card[i] !== null ? card[i] : '-'}${p}</span><div class="custom-tip" style="display:none;"></div></div>`;
    });
    h += `<div class="total-score"><span>TOTAL</span><span>${totals.total}</span></div>`;

    const isCurrentTurn = (typeof isMultiplayer !== 'undefined' && isMultiplayer) ? (isMine ? isMyTurn() : !isMyTurn()) : isMine;
    const titleStyle = isCurrentTurn ? 'color: #00ff00; text-shadow: 0 0 20px rgba(0, 255, 0, 0.8); font-weight: bold;' : 'color: #00ffcc;';

    return `<div class="scorecard-title" style="${titleStyle}">${escapeHtml(title)}</div><div>${h}</div>`;
}

function getScoreMeta(categoryName) {
    return {
        desc: CAT_DESC[categoryName] || '',
        diceEx: CAT_DICE[categoryName] ? `예시) ${CAT_DICE[categoryName]}` : '',
    };
}

function getTooltipHandlers() {
    return [
        'onmouseenter="showTip(this)"',
        'onmouseleave="hideTip()"',
        'onpointerdown="showTip(this)"',
        'ontouchstart="showTip(this)"',
        'ontouchend="hideTip()"',
        'onfocus="showTip(this)"',
        'onblur="hideTip()"',
    ].join(' ');
}

function getScorePreviewHandlers(categoryIndex) {
    return [
        `onmouseenter="showTip(this); previewScore(${categoryIndex})"`,
        'onmouseleave="hideTip(); clearPreview()"',
        `onpointerdown="showTip(this); previewScore(${categoryIndex})"`,
        `ontouchstart="showTip(this); previewScore(${categoryIndex})"`,
        'ontouchend="hideTip(); clearPreview()"',
        `onfocus="showTip(this); previewScore(${categoryIndex})"`,
        'onblur="hideTip(); clearPreview()"',
    ].join(' ');
}

function handleScoreKey(event, categoryIndex) {
    if (!event || (event.key !== 'Enter' && event.key !== ' ')) return;
    event.preventDefault();
    pickCategory(categoryIndex);
}

function applyScoreTooltipChrome(tooltip) {
    tooltip.style.position = 'fixed';
    tooltip.style.display = 'none';
    tooltip.style.background = '#070b16';
    tooltip.style.backgroundColor = '#070b16';
    tooltip.style.opacity = '1';
    tooltip.style.color = '#ffffff';
    tooltip.style.padding = '14px 18px 13px 18px';
    tooltip.style.borderRadius = '10px';
    tooltip.style.fontSize = '1em';
    tooltip.style.fontWeight = '700';
    tooltip.style.lineHeight = '1.55';
    tooltip.style.boxShadow = '0 18px 48px rgba(0,0,0,0.74), 0 0 0 2px rgba(126,243,203,0.95)';
    tooltip.style.zIndex = '5000';
    tooltip.style.whiteSpace = 'pre-line';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.height = 'auto';
    tooltip.style.textAlign = 'left';
    tooltip.style.fontFamily = 'inherit';
    tooltip.style.backdropFilter = 'none';
    tooltip.style.webkitBackdropFilter = 'none';
    tooltip.style.overflowWrap = 'break-word';
    tooltip.style.wordBreak = 'keep-all';
    tooltip.style.border = '1px solid #b5ffe9';
    tooltip.style.overflow = 'auto';
    tooltip.style.maxHeight = '40vh';
    tooltip.style.boxSizing = 'border-box';
    tooltip.style.textShadow = '0 1px 1px rgba(0,0,0,0.85)';
}

function getGlobalTooltip() {
    let tooltip = document.getElementById('global-score-tooltip');
    if (tooltip) {
        applyScoreTooltipChrome(tooltip);
        return tooltip;
    }

    tooltip = document.createElement('div');
    tooltip.id = 'global-score-tooltip';
    applyScoreTooltipChrome(tooltip);
    document.body.appendChild(tooltip);
    return tooltip;
}

function clampTooltipX(left, width, margin = 20) {
    const maxLeft = window.innerWidth - width - margin;
    return Math.max(margin, Math.min(left, maxLeft));
}

function positionScoreTooltip(el, tooltip, scorePreviewLayout) {
    const rect = el.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const margin = window.innerWidth < 600 ? 12 : 20;
    let left = 0;
    let top = 0;

    if (scorePreviewLayout) {
        left = rect.left;
        if (left + tooltipRect.width > window.innerWidth - margin) {
            left = rect.right - tooltipRect.width;
        }
        left = clampTooltipX(left, tooltipRect.width, margin);

        const placeAbove = (window.innerHeight - rect.bottom < tooltipRect.height + 18) && rect.top > tooltipRect.height + 20;
        top = placeAbove ? rect.top - tooltipRect.height - 8 : rect.bottom + 8;
    } else {
        left = clampTooltipX(rect.left + (rect.width * 0.6) - (tooltipRect.width / 2), tooltipRect.width, margin);
        top = rect.top < tooltipRect.height + 20 ? rect.bottom + 10 : rect.top - tooltipRect.height - 10;
    }

    const maxTop = window.innerHeight - tooltipRect.height - margin;
    tooltip.style.left = `${Math.max(margin, Math.min(left, window.innerWidth - tooltipRect.width - margin))}px`;
    tooltip.style.top = `${Math.max(margin, Math.min(top, maxTop))}px`;
}

function getTurnTitleStyle(active) {
    return active
        ? 'color: #00ff00; text-shadow: 0 0 20px rgba(0, 255, 0, 0.8); font-weight: bold;'
        : 'color: #00ffcc;';
}

function flashScoreSelection(categoryIndex) {
    const selector = `[data-score-flash="${categoryIndex}"]`;
    document.querySelectorAll(selector).forEach((el) => {
        el.classList.remove('score-commit-flash');
        void el.offsetWidth;
        el.classList.add('score-commit-flash');
        setTimeout(() => el.classList.remove('score-commit-flash'), 520);
    });
}

function buildValueMarkup(value, preview) {
    if (preview !== null && preview !== undefined) {
        return `<span class="compare-score-main">${value}</span><span class="score-preview">(${preview})</span>`;
    }
    return `<span class="compare-score-main">${value}</span>`;
}

function renderCompactScoreRow(card, categoryIndex, options = {}) {
    const categoryName = CATS[categoryIndex];
    const { desc, diceEx } = getScoreMeta(categoryName);
    const clickable = Boolean(options.interactive) && !gameOver && isMyTurn() && card[categoryIndex] === null && rollsLeft < 3;
    const previewScoreValue = clickable ? calcScore(dice, categoryIndex) : null;
    const preview = card[categoryIndex] === null && previewScoreValue !== null ? previewScoreValue : null;
    const valueMarkup = buildValueMarkup(card[categoryIndex] !== null ? card[categoryIndex] : '-', preview);
    const classes = `score-item compact-score-row ${card[categoryIndex] !== null ? 'filled' : ''} ${clickable ? 'compact-clickable' : ''}`;
    const clickAttr = clickable ? `onclick="pickCategory(${categoryIndex})"` : '';
    const keyAttr = clickable ? `role="button" tabindex="0" onkeydown="handleScoreKey(event, ${categoryIndex})"` : 'tabindex="0"';
    const interactionHandlers = clickable ? getScorePreviewHandlers(categoryIndex) : getTooltipHandlers();
    const tipLayoutAttr = clickable ? 'data-tip-layout="score-preview"' : '';
    return `
        <div class="${classes}" data-score-flash="${categoryIndex}" ${keyAttr} ${interactionHandlers} ${clickAttr} ${tipLayoutAttr} data-desc="${escapeHtml(desc)}" data-dice="${escapeHtml(diceEx)}">
            <span class="score-name">${escapeHtml(categoryName)}</span>
            <span class="score-val">${valueMarkup}</span>
            <div class="custom-tip" style="display:none;"></div>
        </div>
    `;
}

function renderSummaryItem(label, value, options = {}) {
    const idAttr = options.id ? ` id="${options.id}"` : '';
    const extraClass = options.extraClass ? ` ${options.extraClass}` : '';
    const desc = options.desc || '';
    return `
        <div class="score-item${extraClass}" ${getTooltipHandlers()} data-desc="${escapeHtml(desc)}" data-dice="">
            <span class="score-name">${escapeHtml(label)}</span>
            <span class="score-val"${idAttr}>${value}</span>
            <div class="custom-tip" style="display:none;"></div>
        </div>
    `;
}

function renderScoreHelpMarkup(desc = '', diceText = '') {
    const hasDetail = Boolean(desc || diceText);
    const title = hasDetail ? '점수 설명' : '점수표 도움말';
    const body = hasDetail
        ? escapeHtml(desc || '이 항목의 점수 계산 예시입니다.')
        : '점수 항목을 누르거나 올리면 계산 설명과 예시가 표시됩니다. 괄호 안 숫자는 지금 제출할 점수입니다.';
    const dice = diceText
        ? `<div class="score-help-dice">${escapeHtml(diceText)}</div>`
        : '';
    return `
        <div class="score-help-kicker">${title}</div>
        ${dice}
        <div class="score-help-main">${body}</div>
    `;
}

function updateScoreHelp(desc = '', diceText = '') {
    const help = document.getElementById('score-desc-area');
    if (!help) return;
    help.innerHTML = renderScoreHelpMarkup(desc, diceText);
}

function renderCompactSingleCard(card, title, options = {}) {
    const totals = calcTotals(card);
    const titleStyle = getTurnTitleStyle(options.active !== false);
    const showSectionHeads = options.showSectionHeads !== false;
    const upperRows = CATS.slice(0, 6).map((_, index) => renderCompactScoreRow(card, index, { interactive: options.interactive !== false })).join('');
    const lowerRows = CATS.slice(6).map((_, index) => renderCompactScoreRow(card, index + 6, { interactive: options.interactive !== false })).join('');
    const flatRows = `${upperRows}<div class="compact-score-divider"><span>63점 보너스 체크</span></div>${lowerRows}`;
    const layoutClass = showSectionHeads ? 'compact-score-layout' : 'compact-score-layout no-section-heads';
    const sectionsMarkup = showSectionHeads
        ? `
            <div class="compact-score-section">
                <div class="compact-score-head">Upper</div>
                ${upperRows}
            </div>
            <div class="compact-score-section">
                <div class="compact-score-head">Lower</div>
                ${lowerRows}
            </div>
        `
        : `
            <div class="compact-score-section compact-score-section-flat">
                ${flatRows}
            </div>
        `;
    return `
        <div class="scorecard-title" style="${titleStyle}">${escapeHtml(title)}</div>
        ${renderSingleScoreOverview(card, totals, { previewIds: options.previewIds })}
        <div class="${layoutClass}">
            ${sectionsMarkup}
        </div>
    `;
}

function renderCompareStatRow(label, leftValue, rightValue, options = {}) {
    const leftIdAttr = options.leftId ? ` id="${options.leftId}"` : '';
    const desc = options.desc || '';
    const extraClass = options.extraClass ? ` ${options.extraClass}` : '';
    return `
        <div class="compare-row${extraClass}">
            <div class="compare-cat-cell tip-trigger" ${getTooltipHandlers()} data-desc="${escapeHtml(desc)}" data-dice="">
                ${escapeHtml(label)}
                <div class="custom-tip" style="display:none;"></div>
            </div>
            <div class="compare-value-cell"><span class="compare-score-main"${leftIdAttr}>${leftValue}</span></div>
            <div class="compare-value-cell"><span class="compare-score-main">${rightValue}</span></div>
        </div>
    `;
}

function renderCompareCategoryRow(categoryIndex, leftCard, rightCard, options = {}) {
    const categoryName = CATS[categoryIndex];
    const { desc, diceEx } = getScoreMeta(categoryName);
    const clickable = Boolean(options.leftInteractive) && !gameOver && isMyTurn() && leftCard[categoryIndex] === null && rollsLeft < 3;
    const preview = clickable ? calcScore(dice, categoryIndex) : null;
    const leftValueMarkup = buildValueMarkup(leftCard[categoryIndex] !== null ? leftCard[categoryIndex] : '-', leftCard[categoryIndex] === null ? preview : null);
    const rightValueMarkup = buildValueMarkup(rightCard[categoryIndex] !== null ? rightCard[categoryIndex] : '-', null);
    const leftCellClasses = `compare-value-cell ${leftCard[categoryIndex] !== null ? 'filled' : ''} ${clickable ? 'clickable' : ''}`;
    const rightCellClasses = `compare-value-cell ${rightCard[categoryIndex] !== null ? 'filled' : ''}`;
    const clickAttr = clickable ? `onclick="pickCategory(${categoryIndex})"` : '';
    const previewHandlers = clickable ? getScorePreviewHandlers(categoryIndex) : '';
    const keyAttr = clickable ? `role="button" tabindex="0" onkeydown="handleScoreKey(event, ${categoryIndex})"` : '';
    const tipLayoutAttr = clickable ? 'data-tip-layout="score-preview"' : '';
    const scoreMetaAttrs = clickable ? `data-desc="${escapeHtml(desc)}" data-dice="${escapeHtml(diceEx)}"` : '';
    return `
        <div class="compare-row">
            <div class="compare-cat-cell tip-trigger" ${getTooltipHandlers()} data-desc="${escapeHtml(desc)}" data-dice="${escapeHtml(diceEx)}">
                ${escapeHtml(categoryName)}
                <div class="custom-tip" style="display:none;"></div>
            </div>
            <div class="${leftCellClasses}" data-score-flash="${categoryIndex}" ${keyAttr} ${clickAttr} ${previewHandlers} ${tipLayoutAttr} ${scoreMetaAttrs}>${leftValueMarkup}</div>
            <div class="${rightCellClasses}">${rightValueMarkup}</div>
        </div>
    `;
}

function renderCompareBoard(leftCard, rightCard, options = {}) {
    const leftTotals = calcTotals(leftCard);
    const rightTotals = calcTotals(rightCard);
    const leftTitleStyle = getTurnTitleStyle(Boolean(options.leftActive));
    const rightTitleStyle = getTurnTitleStyle(Boolean(options.rightActive));

    let rows = '';
    for (let i = 0; i < CATS.length; i++) {
        if (i === 0) {
            rows += '<div class="compare-section-row"><span>Upper Section</span><em>63점 보너스 흐름</em></div>';
        }
        if (i === 6) {
            rows += '<div class="compare-section-row lower"><span>Lower Section</span><em>족보 점수와 고점</em></div>';
        }
        rows += renderCompareCategoryRow(i, leftCard, rightCard, {
            leftInteractive: options.leftInteractive,
        });
    }
    rows += renderCompareStatRow('TOTAL', `${leftTotals.total}`, `${rightTotals.total}`, {
        extraClass: ' compare-total',
        desc: '상단 합계, 보너스, 하단 점수를 모두 더한 최종 합계입니다.',
    });

    return `
        <div class="compare-board">
            ${renderCompareOverview(leftCard, rightCard, leftTotals, rightTotals, {
                previewIds: options.previewIds,
                leftShortLabel: options.leftShortLabel || '나',
                rightShortLabel: options.rightShortLabel || '상대',
            })}
            <div class="compare-board-head">
                <div class="compare-cat-head">카테고리</div>
                <div class="compare-side-head" style="${leftTitleStyle}">${escapeHtml(options.leftTitle || '나')}</div>
                <div class="compare-side-head" style="${rightTitleStyle}">${escapeHtml(options.rightTitle || '상대')}</div>
            </div>
            ${rows}
        </div>
    `;
}

// 점수 설명은 점수판 상단의 고정 높이 인라인 도움말(#score-desc-area)에만 표시한다.
// (예전에는 커서를 따라다니는 플로팅 툴팁도 같이 띄워 설명이 중복되고 행을 가렸다.)
function showTip(el) {
    const desc = el.getAttribute('data-desc') || '';
    const diceText = el.getAttribute('data-dice') || '';
    if (!desc && !diceText) return;
    updateScoreHelp(desc, diceText);
}

function hideTip() {
    const tip = document.getElementById('global-score-tooltip');
    if (tip) {
        tip.style.display = 'none';
        tip.innerHTML = '';
    }
}

function formatSignedDelta(value) {
    const numeric = Number(value) || 0;
    return numeric >= 0 ? `+${numeric}` : `${numeric}`;
}

function buildOverviewPreviewValue(current, delta, next) {
    return `
        <span class="score-overview-main">${escapeHtml(current)}</span>
        <span class="score-preview-delta">${escapeHtml(formatSignedDelta(delta))} &rarr; ${escapeHtml(next)}</span>
    `;
}

function previewScore(i) {
    if (myCard[i] !== null || rollsLeft === 3 || gameOver) return;
    const sc = calcScore(dice, i);
    const curTotals = calcTotals(myCard);
    const temp = [...myCard];
    temp[i] = sc;
    const newTotals = calcTotals(temp);

    const totalEl = document.getElementById('summary-total') || document.querySelector('.scorecard-area .total-score span:last-child');
    if (totalEl) {
        const diff = newTotals.total - curTotals.total;
        totalEl.classList.add('previewing');
        totalEl.innerHTML = buildOverviewPreviewValue(`${curTotals.total}`, diff, `${newTotals.total}`);
    }

    const subtotalEl = document.getElementById('summary-subtotal') || document.querySelector('.score-item.subtotal .score-val');
    if (subtotalEl) {
        const diff = newTotals.upper - curTotals.upper;
        subtotalEl.classList.add('previewing');
        subtotalEl.innerHTML = buildOverviewPreviewValue(`${curTotals.upper}/63`, diff, `${newTotals.upper}/63`);
    }

    const bonusEl = document.getElementById('summary-bonus') || document.querySelector('.score-item.bonus .score-val');
    if (bonusEl) {
        bonusEl.classList.add('previewing');
        if (newTotals.bonus > curTotals.bonus) {
            bonusEl.innerHTML = buildOverviewPreviewValue(`+${curTotals.bonus}`, newTotals.bonus - curTotals.bonus, `+${newTotals.bonus}`);
            bonusEl.parentElement.style.background = 'rgba(255, 215, 0, 0.25)';
        } else if (newTotals.bonus > 0) {
            bonusEl.innerHTML = `<span class="score-overview-main">+${newTotals.bonus}</span>`;
        } else {
            bonusEl.innerHTML = `<span class="score-overview-main">${Math.max(0, 63 - newTotals.upper)} 남음</span>`;
        }
    }
}

function clearPreview() {
    if (typeof updateScorecard === 'function') updateScorecard();
}
