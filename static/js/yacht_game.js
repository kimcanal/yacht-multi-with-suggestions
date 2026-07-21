/**
 * static/js/yacht_game.js
 * Yacht 게임의 공통 로직 및 유틸리티 함수
 */

function playTurnToastSound() {
    withGameAudio((ctx) => {
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
    });
}

function playKeepSound() {
    withGameAudio((ctx) => {
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
    });
}

let gameAudioContext = null;

function getGameAudioContext() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    gameAudioContext = gameAudioContext || new AudioContextClass();
    return gameAudioContext;
}

function withGameAudio(play) {
    const ctx = getGameAudioContext();
    if (!ctx) return;
    const safelyPlay = () => {
        try {
            play(ctx);
        } catch (error) {
            console.warn('game audio unavailable', error);
        }
    };
    if (ctx.state === 'suspended') {
        ctx.resume().then(safelyPlay).catch((error) => console.warn('game audio unavailable', error));
    } else {
        safelyPlay();
    }
}

function playScoreSelectSound() {
    withGameAudio((ctx) => {
        const now = ctx.currentTime;
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(860, now);
        oscillator.frequency.exponentialRampToValueAtTime(1180, now + 0.12);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
        oscillator.connect(gain).connect(ctx.destination);
        oscillator.start(now);
        oscillator.stop(now + 0.18);
    });
}

function playDiceRollSound() {
    withGameAudio((ctx) => {
        const now = ctx.currentTime;
        const duration = 0.4;
        const noiseBuffer = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * duration), ctx.sampleRate);
        const output = noiseBuffer.getChannelData(0);
        for (let i = 0; i < output.length; i++) output[i] = Math.random() * 2 - 1;

        const noise = ctx.createBufferSource();
        const noiseGain = ctx.createGain();
        noise.buffer = noiseBuffer;
        noiseGain.gain.setValueAtTime(0.2, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        noise.connect(noiseGain).connect(ctx.destination);
        noise.start(now);
        noise.stop(now + duration);

        for (let beat = 0; beat < 5; beat++) {
            const oscillator = ctx.createOscillator();
            const gain = ctx.createGain();
            const startAt = now + beat * 0.07;
            oscillator.type = 'square';
            oscillator.frequency.setValueAtTime(Math.max(1180 - beat * 160, 400), startAt);
            gain.gain.setValueAtTime(0.12, startAt);
            gain.gain.exponentialRampToValueAtTime(0.001, startAt + 0.08);
            oscillator.connect(gain).connect(ctx.destination);
            oscillator.start(startAt);
            oscillator.stop(startAt + 0.08);
        }
    });
}

function renderDice() {
    const dotMap = {
        1: [5], 2: [1,9], 3: [1,5,9], 4: [1,3,7,9], 5: [1,3,5,7,9], 6: [1,3,4,6,7,9]
    };

    const g = document.getElementById('dice-grid');
    g.innerHTML = CATS.slice(0,5).map((_, i) => `
        <div class="dice-item" id="dice-item-${i}">
            <div class="die-container" id="die-container-${i}">
                <div class="die" id="die-${i}" data-value="1">
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

function parseAiScoreValue(scoreRow) {
    const rawScore = Number(scoreRow?.score);
    if (Number.isFinite(rawScore)) return rawScore;
    const match = String(scoreRow?.val_str || '').trim().match(/^(-?\d+(?:\.\d+)?)점$/);
    return match ? Number(match[1]) : null;
}

function getCurrentAiTargetScore(categoryIndex, targetRow) {
    if (
        typeof calcScore === 'function'
        && typeof dice !== 'undefined'
        && Array.isArray(dice)
        && dice.length === 5
    ) {
        const liveScore = Number(calcScore(dice, categoryIndex));
        if (Number.isFinite(liveScore)) return liveScore;
    }
    return parseAiScoreValue(targetRow);
}

function isAiScoreSacrifice(categoryIndex, targetRow) {
    const targetScore = getCurrentAiTargetScore(categoryIndex, targetRow);
    if (targetScore !== null) return targetScore <= 0;
    return targetRow?.type === 'sacrifice';
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
        isSacrifice: isAiScoreSacrifice(categoryIndex, targetRow),
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
