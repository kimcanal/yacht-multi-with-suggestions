/**
 * static/js/shared_turn_ui.js
 *
 * UI helpers shared between single-game.js and multi-game.js. Loaded as a
 * classic (non-module) script, so it reads/writes the same top-level `let`
 * bindings (dice, kept, rollsLeft, gameOver, isRolling, timerInterval, ...)
 * that each page script declares — the same cross-script free-variable
 * pattern yacht_game.js already relies on (see its `typeof dice !== "undefined"`
 * guard). Guard any binding that isn't declared on both pages with
 * `typeof x !== 'undefined'` before reading it.
 *
 * Each page must additionally define:
 *   - isMyTurn()            — turn-ownership check (both pages already do)
 *   - commitKeptChange()     — persist a `kept` mutation (single: commitState();
 *                              multi: GameState.setKept(kept))
 * `isObserver` is optional (multi-only); defaults to false when undeclared.
 */

function clearTurnTimer() {
    if (typeof timerInterval !== 'undefined' && timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    const timerBar = document.getElementById('timer-bar');
    if (timerBar) timerBar.style.display = 'none';
}

function showToast(category, score, note = '') {
    const toast = document.getElementById('score-toast');
    if (!toast) return;
    const noteLine = note
        ? `<div class="toast-cat" style="margin-top:8px; color:#ffd36b;">${escapeHtml(note)}</div>`
        : '';
    toast.innerHTML = `<div class="toast-cat">${escapeHtml(category)}</div><div class="toast-score">+${score}</div>${noteLine}`;
    toast.classList.add('show');
    playScoreSelectSound();
    setTimeout(() => toast.classList.remove('show'), 1500);
}

/**
 * Renders the five dice faces and their KEEP buttons from the current
 * dice/kept/rollsLeft/gameOver/isRolling bindings. Each page's own
 * updateDice() calls this for the shared per-die part, then handles its
 * own AI-hint-enabling condition, roll-btn state, and quick-score-targets
 * tail separately (those genuinely differ: single gates AI hints on the
 * user's coachEnabled toggle, multi always shows them to non-observers).
 */
function renderDiceFaces() {
    const observerActive = typeof isObserver !== 'undefined' && isObserver;
    for (let i = 0; i < 5; i++) {
        const dieEl = document.getElementById(`die-${i}`);
        const containerEl = document.getElementById(`die-container-${i}`);
        if (!dieEl || !containerEl) continue;

        containerEl.classList.toggle('dice-unrolled', rollsLeft === 3 && !isRolling && !gameOver);
        if (isRolling && !kept[i]) {
            dieEl.classList.add('rolling');
        } else {
            dieEl.classList.remove('rolling');
        }

        if (kept[i]) {
            containerEl.classList.add('locked');
            dieEl.querySelectorAll('.die-face').forEach((face) => {
                face.style.borderColor = '#00ffcc';
            });
        } else {
            containerEl.classList.remove('locked');
            dieEl.querySelectorAll('.die-face').forEach((face) => {
                face.style.borderColor = 'rgba(200,200,200,0.5)';
            });
        }

        dieEl.dataset.value = String(dice[i] || 1);

        const keepBtn = document.getElementById(`keep-${i}`);
        const keepText = document.getElementById(`keep-text-${i}`);
        if (keepBtn && keepText) {
            keepBtn.className = 'keep-btn';
            const disabled = observerActive || rollsLeft >= 3 || rollsLeft === 0 || gameOver || isRolling || !isMyTurn();
            keepBtn.disabled = disabled;
            keepBtn.style.opacity = disabled ? '0.5' : '1';
            keepBtn.style.cursor = disabled ? 'not-allowed' : 'pointer';
            keepBtn.style.boxShadow = 'none';

            if (kept[i]) {
                keepBtn.classList.add('active-keep');
                keepBtn.style.borderColor = '#00ff00';
            } else {
                keepBtn.style.borderColor = 'rgba(255, 255, 255, 0.3)';
            }

            keepText.innerHTML = kept[i] ? '✓ KEEP' : 'KEEP';
        }

        const label = document.getElementById(`lock-${i}`);
        if (label) label.innerText = '';
    }
}

function toggleLock(i) {
    const observerActive = typeof isObserver !== 'undefined' && isObserver;
    if (observerActive || rollsLeft >= 3 || rollsLeft <= 0 || gameOver || isRolling || !isMyTurn()) return;
    kept[i] = kept[i] ? 0 : 1;
    commitKeptChange();
    updateDice();
    pushState();
    playKeepSound();
}

function applyAiKeepTarget(target) {
    const observerActive = typeof isObserver !== 'undefined' && isObserver;
    if (observerActive || rollsLeft >= 3 || rollsLeft <= 0 || gameOver || isRolling || !isMyTurn()) return;
    if (!Array.isArray(target) || target.length !== 5) return;
    for (let i = 0; i < 5; i++) kept[i] = target[i] ? 1 : 0;
    commitKeptChange();
    updateDice();
    pushState();
    playKeepSound();
}
window.applyAiKeepTarget = applyAiKeepTarget;
