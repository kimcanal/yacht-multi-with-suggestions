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
        if (i === 6) {
            h += `<div class="score-item subtotal" style="background:rgba(255,255,255,0.1); cursor:default; min-width:140px;" data-desc="상단 항목의 점수 합계.\n목표는 63점 (각 숫자 3개씩)" title="상단 항목의 점수 합계.\n목표는 63점 (각 숫자 3개씩)" data-dice="" onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"><span class="score-name">Subtotal</span><span class="score-val">${totals.upper}/63</span><div class='custom-tip' style='display:none;'></div></div>`;
            h += `<div class="score-item bonus" style="min-width:140px;" data-desc="상단 합계 63점 이상 \n→ 보너스 35점" title="상단 합계 63점 이상 \n→ 보너스 35점" data-dice="" onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"><span class="score-name">Upper Bonus</span><span class="score-val">+${totals.bonus}</span><div class='custom-tip' style='display:none;'></div></div>`;
        }
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
    return `onmouseenter="showTip(this)" onmouseleave="hideTip(this)" ontouchstart="showTip(this)" ontouchend="hideTip(this)"`;
}

function getPreviewHandlers(categoryIndex) {
    return `onmouseenter="previewScore(${categoryIndex})" onmouseleave="clearPreview()" ontouchstart="previewScore(${categoryIndex})" ontouchend="clearPreview()"`;
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
    if (preview) {
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
    const previewHandlers = clickable ? getPreviewHandlers(categoryIndex) : '';
    const tipLayoutAttr = clickable ? 'data-tip-layout="score-preview"' : '';
    return `
        <div class="${classes}" data-score-flash="${categoryIndex}" ${getTooltipHandlers()} ${clickAttr} ${previewHandlers} ${tipLayoutAttr} data-desc="${escapeHtml(desc)}" data-dice="${escapeHtml(diceEx)}">
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
        <div class="${layoutClass}">
            ${sectionsMarkup}
        </div>
        <div class="compact-summary-grid">
            ${renderSummaryItem('Subtotal', `${totals.upper}/63`, {
                id: options.previewIds ? 'summary-subtotal' : '',
                extraClass: 'subtotal compact-summary-card',
                desc: '상단 항목의 점수 합계. 목표는 63점입니다.',
            })}
            ${renderSummaryItem('Upper Bonus', `+${totals.bonus}`, {
                id: options.previewIds ? 'summary-bonus' : '',
                extraClass: 'bonus compact-summary-card',
                desc: '상단 합계 63점 이상이면 보너스 35점을 받습니다.',
            })}
            <div class="total-score compact-total">
                <span>TOTAL</span>
                <span${options.previewIds ? ' id="summary-total"' : ''}>${totals.total}</span>
            </div>
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
    const previewHandlers = clickable ? getPreviewHandlers(categoryIndex) : '';
    return `
        <div class="compare-row">
            <div class="compare-cat-cell tip-trigger" ${getTooltipHandlers()} data-desc="${escapeHtml(desc)}" data-dice="${escapeHtml(diceEx)}">
                ${escapeHtml(categoryName)}
                <div class="custom-tip" style="display:none;"></div>
            </div>
            <div class="${leftCellClasses}" data-score-flash="${categoryIndex}" ${clickAttr} ${previewHandlers}>${leftValueMarkup}</div>
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
        if (i === 6) {
            rows += renderCompareStatRow('Subtotal', `${leftTotals.upper}/63`, `${rightTotals.upper}/63`, {
                leftId: options.previewIds ? 'summary-subtotal' : '',
                extraClass: ' compare-summary',
                desc: '상단 항목의 점수 합계입니다. 목표는 63점입니다.',
            });
            rows += renderCompareStatRow('Upper Bonus', `+${leftTotals.bonus}`, `+${rightTotals.bonus}`, {
                leftId: options.previewIds ? 'summary-bonus' : '',
                extraClass: ' compare-summary',
                desc: '상단 합계 63점 이상이면 보너스 35점을 받습니다.',
            });
        }
        rows += renderCompareCategoryRow(i, leftCard, rightCard, {
            leftInteractive: options.leftInteractive,
        });
    }
    rows += renderCompareStatRow('TOTAL', `${leftTotals.total}`, `${rightTotals.total}`, {
        leftId: options.previewIds ? 'summary-total' : '',
        extraClass: ' compare-total',
        desc: '상단 합계, 보너스, 하단 점수를 모두 더한 최종 합계입니다.',
    });

    return `
        <div class="compare-board">
            <div class="compare-board-head">
                <div class="compare-cat-head">카테고리</div>
                <div class="compare-side-head" style="${leftTitleStyle}">${escapeHtml(options.leftTitle || '나')}</div>
                <div class="compare-side-head" style="${rightTitleStyle}">${escapeHtml(options.rightTitle || '상대')}</div>
            </div>
            ${rows}
        </div>
    `;
}

function showTip(el) {
    hideTip(el);
    const desc = el.getAttribute('data-desc') || '';
    const diceText = el.getAttribute('data-dice') || '';
    if (!desc && !diceText) return;
    const tip = el.querySelector('.custom-tip');
    if (tip) {
        const tipLayout = el.getAttribute('data-tip-layout') || 'default';
        const scorePreviewLayout = tipLayout === 'score-preview';
        tip.style.display = 'flex';
        tip.style.flexDirection = 'column';
        tip.style.alignItems = 'flex-start';
        const diceMarkup = diceText
            ? `<div class="tip-dice" style="font-weight:800; color:#7ef3cb; font-size:1.04em; margin-bottom:6px;">${diceText}</div>`
            : '';
        tip.innerHTML = `${diceMarkup}<div class="tip-desc" style="font-size:1.01em; line-height:1.6; color:#f8fbff; font-weight:600;">${desc}</div>`;
        tip.style.position = 'absolute';
        const rect = el.getBoundingClientRect();
        const tipHeight = 80;
        tip.style.left = '';
        tip.style.right = '';
        tip.style.top = '';
        tip.style.bottom = '';
        tip.style.marginTop = '0';
        if (scorePreviewLayout) {
            const placeAbove = (window.innerHeight - rect.bottom < 150) && rect.top > 140;
            const alignRight = rect.left + 340 > window.innerWidth - 20;
            if (alignRight) {
                tip.style.right = '0';
            } else {
                tip.style.left = '0';
            }
            tip.style.transform = 'none';
            tip.style.width = 'min(320px, calc(100vw - 40px))';
            tip.style.minWidth = '180px';
            tip.style.maxWidth = '320px';
            if (placeAbove) {
                tip.style.bottom = 'calc(100% + 8px)';
            } else {
                tip.style.top = 'calc(100% + 8px)';
            }
        } else {
            tip.style.left = '60%';
            if (rect.top < tipHeight) {
                tip.style.top = '100%';
                tip.style.marginTop = '10px';
            } else {
                tip.style.top = '-64px';
            }
            tip.style.transform = 'translateX(-50%)';
            tip.style.minWidth = '180px';
            tip.style.maxWidth = '320px';
            tip.style.width = 'max-content';
        }
        tip.style.background = '#16192f';
        tip.style.opacity = '1';
        tip.style.color = '#f8fbff';
        tip.style.padding = '14px 18px 13px 18px';
        tip.style.borderRadius = '12px';
        tip.style.fontSize = '1em';
        tip.style.boxShadow = '0 16px 36px rgba(0,0,0,0.46), 0 0 0 1px rgba(126,243,203,0.18)';
        tip.style.zIndex = '1500';
        tip.style.whiteSpace = 'pre-line';
        tip.style.pointerEvents = 'none';
        tip.style.height = 'auto';
        tip.style.textAlign = 'left';
        tip.style.fontFamily = 'inherit';
        tip.style.backdropFilter = 'none';
        tip.style.webkitBackdropFilter = 'none';
        tip.style.overflowWrap = 'break-word';
        tip.style.wordBreak = 'keep-all';
        tip.style.border = '1.5px solid #7ef3cb';
        tip.style.overflow = 'visible';
        tip.style.boxSizing = 'border-box';
        if (window.innerWidth < 600) {
            tip.style.fontSize = '0.98em';
            tip.style.padding = '10px 10px 9px 10px';
            tip.style.maxWidth = '90vw';
            tip.style.width = 'auto';
            if (scorePreviewLayout) {
                tip.style.left = '0';
                tip.style.right = '0';
                tip.style.minWidth = '0';
                tip.style.bottom = '';
                tip.style.top = 'calc(100% + 8px)';
                tip.style.transform = 'none';
            } else {
                tip.style.minWidth = '120px';
                tip.style.top = '-54px';
            }
        }
    }
}

function hideTip(el) {
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

    const totalEl = document.getElementById('summary-total') || document.querySelector('.scorecard-area .total-score span:last-child');
    if (totalEl) {
        const diff = newTotals.total - curTotals.total;
        totalEl.innerHTML = `${curTotals.total} <span style="color:#00ffcc; font-size:0.8em"> (+${diff}) ➜ ${newTotals.total}</span>`;
    }

    const subtotalEl = document.getElementById('summary-subtotal') || document.querySelector('.score-item.subtotal .score-val');
    if (subtotalEl) {
        const diff = newTotals.upper - curTotals.upper;
        subtotalEl.innerHTML = `${curTotals.upper}/63 <span style="color:#00ffcc; font-size:0.8em"> (+${diff}) ➜ ${newTotals.upper}/63</span>`;
    }

    const bonusEl = document.getElementById('summary-bonus') || document.querySelector('.score-item.bonus .score-val');
    if (bonusEl && newTotals.bonus > curTotals.bonus) {
        bonusEl.innerHTML = `+${curTotals.bonus} <span style="color:#ffd700; font-weight:bold"> (+35) ➜ ${newTotals.bonus}</span>`;
        bonusEl.parentElement.style.background = 'rgba(255, 215, 0, 0.25)';
    }
}

function clearPreview() {
    if (typeof updateScorecard === 'function') updateScorecard();
}
