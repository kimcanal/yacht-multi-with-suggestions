/**
 * static/js/ai_panel.js
 * 추천 패널 렌더링 및 모드 토글
 */

const AI_MODE_KEY = 'yacht_ai_mode';
const AI_PANEL_EXPANDED_KEY = 'yacht_ai_panel_expanded';
const AI_PANEL_CACHE = {};

function normalizeAiMode(mode) {
    return mode === 'cover' ? 'cover' : 'focused';
}

function getAiMode() {
    return normalizeAiMode(localStorage.getItem(AI_MODE_KEY));
}

function setAiMode(mode) {
    localStorage.setItem(AI_MODE_KEY, normalizeAiMode(mode));
}

function isAiPanelExpanded() {
    return localStorage.getItem(AI_PANEL_EXPANDED_KEY) === 'true';
}

function setAiPanelExpanded(value) {
    localStorage.setItem(AI_PANEL_EXPANDED_KEY, value ? 'true' : 'false');
}

function toggleAiPanelExpanded(targetId = 'ai-breakdown') {
    setAiPanelExpanded(!isAiPanelExpanded());
    const cached = AI_PANEL_CACHE[targetId];
    if (cached) {
        renderAiPanel(targetId, cached.aiRec, cached.options);
    }
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

function getAiStageLabel(aiRec) {
    return aiRec?.stage === 'score' ? '기록 단계' : '굴림 단계';
}

function getAiModeLabel(aiRec) {
    return aiRec?.strategy_mode === 'cover' ? '커버 플레이' : '집중 공략';
}

function getAiPrimaryText(aiRec) {
    if (aiRec?.message && aiRec.message !== '점수 기록 단계') return aiRec.message;
    if (aiRec?.primary_target) return aiRec.primary_target;
    if (Array.isArray(aiRec?.breakdown) && aiRec.breakdown[0]?.name) return aiRec.breakdown[0].name;
    return '추천 계산 중';
}

function renderAiRowCard(item, isScoreStage, showReason) {
    const color = getAiRowColor(item);
    const reason = item.reason && showReason
        ? `<div class="ai-row-reason">${escapeHtml(item.reason)}</div>`
        : '';
    const progress = isScoreStage ? '' : `
        <div class="ai-row-bar">
            <div class="ai-row-bar-fill" style="background:${color}; width:${getAiRowMeter(item) * 100}%"></div>
        </div>
    `;

    return `
        <div class="ai-breakdown-card">
            <div class="ai-row-head">
                <span class="ai-row-name">${escapeHtml(item.name || '')}</span>
                <span class="breakdown-val" style="color:${color};">${escapeHtml(item.val_str || '')}</span>
            </div>
            <div class="ai-row-keep">${escapeHtml(item.keep_str || '')}</div>
            ${progress}
            ${reason}
        </div>
    `;
}

function renderAiPanel(targetId, aiRec, options = {}) {
    const root = document.getElementById(targetId);
    if (!root) return;
    AI_PANEL_CACHE[targetId] = {
        aiRec,
        options: { ...options },
    };
    if (!aiRec || !aiRec.breakdown || aiRec.breakdown.length === 0) {
        root.innerHTML = '<div style="color:#999; text-align:center; padding:12px; font-size:0.9em;">대기 중...</div>';
        return;
    }

    const isScoreStage = aiRec?.stage === 'score';
    const expanded = isAiPanelExpanded();
    const visibleCount = expanded ? 5 : 2;
    const rowsToShow = aiRec.breakdown.slice(0, visibleCount);
    const hiddenCount = Math.max(0, Math.min(aiRec.breakdown.length, 5) - rowsToShow.length);
    const summary = aiRec.summary ? `<div class="ai-summary-line">${escapeHtml(aiRec.summary)}</div>` : '';
    const perspective = options.perspective ? `<div class="ai-perspective">${escapeHtml(options.perspective)}</div>` : '';
    const safeTargetId = String(targetId).replace(/'/g, "\\'");
    const shouldShowToggle = aiRec.breakdown.length > 2;
    const toggleLabel = expanded ? '간단히 보기' : `상세 ${hiddenCount > 0 ? `+${hiddenCount}` : ''}`;
    const toggleButton = shouldShowToggle ? `
        <button type="button" class="ai-panel-toggle" onclick="toggleAiPanelExpanded('${safeTargetId}')" aria-expanded="${expanded ? 'true' : 'false'}">
            ${toggleLabel}
        </button>
    ` : '';
    const rows = rowsToShow.map((item, index) => renderAiRowCard(item, isScoreStage, expanded || index === 0)).join('');
    const moreNote = !expanded && hiddenCount > 0
        ? `<div class="ai-more-note">핵심 2개만 먼저 보여주고 있어요. 상세를 열면 나머지 후보도 볼 수 있습니다.</div>`
        : '';

    root.innerHTML = `
        <div class="ai-panel-shell">
            <div class="ai-panel-head">
                <div>
                    <div class="ai-panel-title">${getAiPanelTitle(aiRec)}</div>
                    ${perspective}
                </div>
                ${toggleButton}
            </div>
            <div class="ai-summary-band">
                <div class="ai-summary-main">
                    <div class="ai-primary-pill">${escapeHtml(getAiPrimaryText(aiRec))}</div>
                    ${summary}
                </div>
                <div class="ai-meta-row">
                    <span class="ai-meta-chip">${escapeHtml(getAiStageLabel(aiRec))}</span>
                    <span class="ai-meta-chip">${escapeHtml(getAiModeLabel(aiRec))}</span>
                </div>
            </div>
            <div class="ai-breakdown-grid">
                ${rows}
            </div>
            ${moreNote}
        </div>
    `;
}
