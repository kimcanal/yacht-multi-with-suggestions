/**
 * static/js/ai_panel.js
 * 추천 패널 렌더링 및 모드 토글
 */

const AI_MODE_KEY = 'yacht_ai_mode';

function getAiMode() {
    const mode = localStorage.getItem(AI_MODE_KEY);
    return mode === 'aggressive' ? 'aggressive' : 'safe';
}

function setAiMode(mode) {
    localStorage.setItem(AI_MODE_KEY, mode === 'aggressive' ? 'aggressive' : 'safe');
}

function updateAiModeButtons(scope = document) {
    const mode = getAiMode();
    scope.querySelectorAll('[data-ai-mode]').forEach((btn) => {
        const active = btn.dataset.aiMode === mode;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
}

function bindAiModeControls(onChange) {
    document.querySelectorAll('[data-ai-mode]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const nextMode = btn.dataset.aiMode === 'aggressive' ? 'aggressive' : 'safe';
            setAiMode(nextMode);
            updateAiModeButtons();
            if (typeof onChange === 'function') onChange(nextMode);
        });
    });
    updateAiModeButtons();
}

function renderAiPanel(targetId, aiRec, options = {}) {
    const root = document.getElementById(targetId);
    if (!root) return;
    if (!aiRec || !aiRec.breakdown || aiRec.breakdown.length === 0) {
        root.innerHTML = '<div style="color:#999; text-align:center; padding:12px; font-size:0.9em;">대기 중...</div>';
        return;
    }

    const summary = aiRec.summary ? `<div class="ai-summary-line">${escapeHtml(aiRec.summary)}</div>` : '';
    const styleLabel = aiRec.strategy_mode === 'aggressive' ? '한방형' : '안전형';
    const perspective = options.perspective ? `<div class="ai-perspective">${escapeHtml(options.perspective)}</div>` : '';
    const rows = aiRec.breakdown.slice(0, 5).map((item) => {
        const color = item.type === 'upper' ? '#8be28b' : '#ffd36b';
        const barWidth = Math.min((item.prob || 0) * 100, 100);
        const reason = item.reason ? `<div class="ai-reason">${escapeHtml(item.reason)}</div>` : '';
        return `
            <div class="breakdown-item">
                <div style="flex:1;">
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px;">
                        <span style="color:#f2f4f8; font-weight:700;">${escapeHtml(item.name)}</span>
                        <span class="breakdown-val" style="color:${color};">${escapeHtml(item.val_str || '')}</span>
                    </div>
                    <div style="font-size:0.88em; color:#98a4b3; margin-bottom:6px;">${escapeHtml(item.keep_str || '')}</div>
                    <div style="background:rgba(255,255,255,0.08); border-radius:999px; height:8px; overflow:hidden;">
                        <div style="background:${color}; border-radius:999px; height:100%; width:${barWidth}%; transition:width 0.35s ease;"></div>
                    </div>
                    ${reason}
                </div>
            </div>
        `;
    }).join('');

    root.innerHTML = `
        <div class="ai-panel-head">
            <div class="ai-panel-title">${styleLabel} 추천</div>
            ${perspective}
        </div>
        ${summary}
        ${rows}
    `;
}
