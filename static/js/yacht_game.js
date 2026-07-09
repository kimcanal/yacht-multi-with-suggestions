/**
 * static/js/yacht_game.js
 * Yacht 게임의 공통 로직 및 유틸리티 함수
 */

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

function removeAiHintBadges(root, selector) {
    root.querySelectorAll(selector).forEach((badge) => badge.remove());
}

function clearAiDiceHints() {
    for (let i = 0; i < 5; i++) {
        const itemEl = document.getElementById(`dice-item-${i}`);
        const containerEl = document.getElementById(`die-container-${i}`);
        const keepBtn = document.getElementById(`keep-${i}`);
        if (itemEl) {
            itemEl.classList.remove('ai-keep-recommended');
            removeAiHintBadges(itemEl, '.ai-dice-badge');
        }
        if (containerEl) containerEl.classList.remove('ai-keep-recommended');
        if (keepBtn) keepBtn.classList.remove('ai-keep-recommended');
    }
}

function clearAiScoreHints() {
    document.querySelectorAll('[data-score-flash]').forEach((el) => {
        el.classList.remove('ai-score-recommended', 'ai-score-sacrifice');
        removeAiHintBadges(el, '.ai-score-badge');
    });
}

function getAiScoreTarget(aiRec) {
    if (!aiRec || typeof aiRec !== 'object') return null;
    const breakdown = Array.isArray(aiRec.breakdown) ? aiRec.breakdown : [];
    const targetName = aiRec.primary_target || (
        aiRec.stage === 'score' && breakdown[0] ? breakdown[0].name : null
    );
    if (!targetName || typeof CATS === 'undefined') return null;
    const categoryIndex = CATS.indexOf(targetName);
    if (categoryIndex < 0) return null;
    const targetRow = breakdown.find((row) => row && row.name === targetName) || breakdown[0] || {};
    return {
        categoryIndex,
        isSacrifice: targetRow.type === 'sacrifice' || Number(targetRow.score) === 0 || String(targetRow.val_str || '').includes('0점'),
    };
}

function isAiScoreHintStage(aiRec) {
    if (!aiRec || typeof aiRec !== 'object') return false;
    if (aiRec.stage === 'score') return true;
    const recs = Array.isArray(aiRec.dice_recommendations) ? aiRec.dice_recommendations : [];
    return recs.length >= 5 && recs.every((rec) => rec && rec.action === 'keep');
}

function applyAiDiceHints(aiRec, options = {}) {
    clearAiDiceHints();
    if (!options.enabled || !aiRec || aiRec.stage === 'score') return;
    const recs = Array.isArray(aiRec.dice_recommendations) ? aiRec.dice_recommendations : [];
    recs.forEach((rec, fallbackIndex) => {
        if (!rec || rec.action !== 'keep') return;
        const index = Number.isInteger(rec.index) ? rec.index : fallbackIndex;
        const itemEl = document.getElementById(`dice-item-${index}`);
        const containerEl = document.getElementById(`die-container-${index}`);
        const keepBtn = document.getElementById(`keep-${index}`);
        if (!itemEl || !containerEl) return;
        itemEl.classList.add('ai-keep-recommended');
        containerEl.classList.add('ai-keep-recommended');
        if (keepBtn) keepBtn.classList.add('ai-keep-recommended');
        if (!itemEl.querySelector('.ai-dice-badge')) {
            const badge = document.createElement('span');
            badge.className = 'ai-dice-badge';
            badge.textContent = 'AI KEEP';
            itemEl.appendChild(badge);
        }
    });
}

function applyAiScoreHints(aiRec, options = {}) {
    clearAiScoreHints();
    if (!options.enabled || !isAiScoreHintStage(aiRec)) return;
    const target = getAiScoreTarget(aiRec);
    if (!target) return;
    document.querySelectorAll(`[data-score-flash="${target.categoryIndex}"]`).forEach((el) => {
        el.classList.add(target.isSacrifice ? 'ai-score-sacrifice' : 'ai-score-recommended');
        if (!el.querySelector('.ai-score-badge')) {
            const badge = document.createElement('span');
            badge.className = 'ai-score-badge';
            badge.textContent = target.isSacrifice ? '희생' : '추천';
            el.appendChild(badge);
        }
    });
}

function applyAiBoardHints(aiRec, options = {}) {
    const enabled = Boolean(options.enabled);
    applyAiDiceHints(aiRec, { enabled });
    applyAiScoreHints(aiRec, { enabled });
}
