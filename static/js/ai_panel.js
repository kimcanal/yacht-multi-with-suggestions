/**
 * static/js/ai_panel.js
 * 추천 패널 렌더링 및 모드 토글
 */

const AI_MODE_KEY = 'yacht_ai_mode';

function normalizeAiMode(mode) {
    return mode === 'cover' ? 'cover' : 'focused';
}

function getAiMode() {
    return normalizeAiMode(localStorage.getItem(AI_MODE_KEY));
}

function setAiMode(mode) {
    localStorage.setItem(AI_MODE_KEY, normalizeAiMode(mode));
}

function updateAiModeButtons(scope = document) {
    const mode = getAiMode();
    scope.querySelectorAll('[data-ai-mode]').forEach((btn) => {
        const active = btn.dataset.aiMode === mode;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    scope.querySelectorAll('[data-ai-mode-desc]').forEach((card) => {
        const active = card.dataset.aiModeDesc === mode;
        card.classList.toggle('active', active);
        card.setAttribute('aria-current', active ? 'true' : 'false');
    });
}

function bindAiModeControls(onChange) {
    document.querySelectorAll('[data-ai-mode]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const nextMode = normalizeAiMode(btn.dataset.aiMode);
            setAiMode(nextMode);
            updateAiModeButtons();
            if (typeof onChange === 'function') onChange(nextMode);
        });
    });
    updateAiModeButtons();
}

function getAiPanelTitle(aiRec) {
    if (aiRec?.stage === 'score') return '점수 기록 추천';
    return aiRec?.strategy_mode === 'cover' ? '커버 플레이 추천' : '집중 공략 추천';
}

function getAiRowColor(item) {
    if (item?.type === 'cover') return '#7ee787';
    if (item?.type === 'risk') return '#ff8e72';
    if (item?.type === 'decision') return '#8fb8ff';
    if (item?.type === 'upper') return '#8be28b';
    if (item?.type === 'score') return '#66d9ff';
    if (item?.type === 'sacrifice') return '#ff9b7a';
    return '#ffd36b';
}

function getAiRowMeter(item) {
    const raw = Number(item?.meter ?? item?.prob ?? 0);
    if (!Number.isFinite(raw)) return 0;
    return Math.max(0, Math.min(raw, 1));
}

function renderAiPanel(targetId, aiRec, options = {}) {
    const root = document.getElementById(targetId);
    if (!root) return;
    if (!aiRec || !aiRec.breakdown || aiRec.breakdown.length === 0) {
        root.innerHTML = '<div style="color:#999; text-align:center; padding:12px; font-size:0.9em;">대기 중...</div>';
        return;
    }

    const isScoreStage = aiRec?.stage === 'score';
    const summary = aiRec.summary ? `<div class="ai-summary-line">${escapeHtml(aiRec.summary)}</div>` : '';
    const perspective = options.perspective ? `<div class="ai-perspective">${escapeHtml(options.perspective)}</div>` : '';
    const rows = aiRec.breakdown.slice(0, 5).map((item) => {
        const color = getAiRowColor(item);
        const reason = item.reason ? `<div class="ai-reason">${escapeHtml(item.reason)}</div>` : '';
        const progress = isScoreStage ? '' : `
                    <div style="background:rgba(255,255,255,0.08); border-radius:999px; height:8px; overflow:hidden;">
                        <div style="background:${color}; border-radius:999px; height:100%; width:${getAiRowMeter(item) * 100}%; transition:width 0.35s ease;"></div>
                    </div>
        `;
        return `
            <div class="breakdown-item">
                <div style="flex:1;">
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px;">
                        <span style="color:#f2f4f8; font-weight:700;">${escapeHtml(item.name)}</span>
                        <span class="breakdown-val" style="color:${color};">${escapeHtml(item.val_str || '')}</span>
                    </div>
                    <div style="font-size:0.88em; color:#98a4b3; margin-bottom:6px;">${escapeHtml(item.keep_str || '')}</div>
                    ${progress}
                    ${reason}
                </div>
            </div>
        `;
    }).join('');

    root.innerHTML = `
        <div class="ai-panel-head">
            <div class="ai-panel-title">${getAiPanelTitle(aiRec)}</div>
            ${perspective}
        </div>
        ${summary}
        ${rows}
    `;
}
