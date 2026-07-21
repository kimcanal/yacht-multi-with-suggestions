/**
 * static/js/ai_panel.js
 * 추천 패널 렌더링 및 모드 토글
 */

const AI_MODE_KEY = 'yacht_ai_mode';
const AI_PANEL_EXPANDED_KEY = 'yacht_ai_panel_expanded';
const AI_PANEL_CACHE = {};

function normalizeAiMode(mode) {
    if (mode === 'cover' || mode === 'optimal') return mode;
    if (mode === 'value_optimal' || mode === 'ev_optimal') return 'optimal';
    return 'focused';
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
    const selectMode = (rawMode) => {
        const nextMode = normalizeAiMode(rawMode);
        setAiMode(nextMode);
        updateAiModeButtons();
        if (typeof onChange === 'function') onChange(nextMode);
    };
    // 버튼 줄(data-ai-mode)과 설명 카드(data-ai-mode-desc) 모두 클릭으로 모드 선택
    document.querySelectorAll('[data-ai-mode]').forEach((btn) => {
        btn.addEventListener('click', () => selectMode(btn.dataset.aiMode));
    });
    document.querySelectorAll('[data-ai-mode-desc]').forEach((card) => {
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.addEventListener('click', () => selectMode(card.dataset.aiModeDesc));
        card.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                selectMode(card.dataset.aiModeDesc);
            }
        });
    });
    updateAiModeButtons();
}

function getAiPanelTitle(aiRec) {
    if (aiRec?.stage === 'score') return '점수 기록 추천';
    if (aiRec?.strategy_mode === 'optimal') return '기대점수 최적 추천';
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
    if (aiRec?.stage === 'done') return '완료';
    return aiRec?.stage === 'score' ? '기록 단계' : '굴림 단계';
}

function getAiModeLabel(aiRec) {
    if (aiRec?.strategy_mode === 'optimal') return '기대점수 최적';
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

function renderAiReportList(items, className = 'ai-report-list') {
    if (!Array.isArray(items) || items.length === 0) return '';
    return `
        <ul class="${className}">
            ${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
        </ul>
    `;
}

const METHOD_LABEL_MAP = {
    'Full-game exact V': '기대 최종점수',
    'Exact solver': '정밀 계산',
    '학습 정책 모델': '학습 모델'
};

const METHOD_NOTE_MAP = {
    '현재 Yacht 상태공간은 작아서 모든 합리적 keep 후보를 동적계획법으로 직접 비교할 수 있습니다.': 
        '현재 주사위 조합별 확률과 이후 점수판에 미칠 영향을 함께 비교했습니다.',
    '점수 기록 단계는 현재 점수와 남은 칸의 장기 가치를 utility로 비교한 계산 결과입니다.':
        '현재 얻는 점수와 남은 칸의 가치를 함께 비교했습니다.',
    '현재 기록 점수와 이번 선택 이후의 기대점수를 합산해 기대 최종점수가 가장 큰 선택을 고릅니다. 이후 기대점수에는 이번 턴의 기록과 남은 모든 턴의 full-game exact V가 포함됩니다.':
        '이번 기록과 남은 턴의 기대 점수를 합쳐 최종 점수가 가장 커지는 선택을 찾았습니다.',
    '이번 굴림 선택은 exact solver가 만든 teacher 데이터를 학습한 정책 모델이 먼저 냈고, confidence 기준을 넘은 경우에만 채택됩니다.':
        '학습 모델의 후보를 검증해 신뢰할 수 있는 경우에만 추천에 반영합니다.'
};

const LEARNING_NOTE_MAP = {
    '이 결정에는 ML/DL 모델이 꼭 필요하지 않습니다. 지금 게임처럼 상태공간이 작으면 exact solver가 teacher 역할을 하며, 모델은 그 결정을 빠르게 근사하거나 상대/승률 같은 더 큰 맥락을 학습할 때 가치가 커집니다.':
        '이 추천은 현재 선택 기준의 여러 가능성을 확률로 비교한 결과입니다.',
    '모델은 스스로 결정을 흉내 내는 실행 정책이고, 낮은 확신이나 위험한 상태에서는 exact solver로 돌아갑니다. 다음 단계의 self-learning은 self-play 데이터를 더 쌓아 win-rate/value model을 붙이는 방식이 좋습니다.':
        '이 추천은 학습 모델의 예측을 사용하며, 확신이 낮거나 위험하면 정밀 계산 결과를 사용합니다.',
    '이 모드는 학습 모델 없이 full-game exact value table을 직접 조회합니다. 현재 목표는 승률이 아니라 기대 최종점수 최대화입니다.':
        '남은 점수판까지 고려해 기대 최종점수가 가장 큰 선택을 찾습니다.'
};

function cleanEvText(text) {
    if (!text) return '';
    return text
        .replace(/EV\s*([0-9.]+)/g, '기대 $1점')
        .replace(/full-game exact V/gi, '정밀 기대 분석')
        .replace(/exact solver/gi, '정밀 확률 계산');
}

function formatAiProbability(value) {
    const probability = Number(value);
    if (!Number.isFinite(probability) || probability < 0 || probability > 1) return '';
    return `${(probability * 100).toFixed(1)}%`;
}

function renderProbabilityContext(context) {
    if (!context || typeof context !== 'object') return '';
    const primaryProbability = formatAiProbability(context.probability);
    if (!context.name || !primaryProbability) return '';
    const supporting = Array.isArray(context.supporting) ? context.supporting
        .map((item) => {
            const probability = formatAiProbability(item?.probability);
            if (!item?.name || !probability) return '';
            return `<span>${escapeHtml(item.name)} ${escapeHtml(probability)}</span>`;
        })
        .filter(Boolean)
        .join('') : '';
    const basis = context.basis
        ? `<div class="ai-probability-basis">${escapeHtml(context.basis)}</div>`
        : '';

    return `
        <div class="ai-probability-card">
            <div class="ai-probability-primary">
                <span>${escapeHtml(context.label || '주목표')}</span>
                <strong>${escapeHtml(context.name)} <em>${escapeHtml(primaryProbability)}</em></strong>
            </div>
            ${supporting ? `<div class="ai-probability-support"><span>함께 가능한 결과</span>${supporting}</div>` : ''}
            ${basis}
        </div>
    `;
}

function renderActionComparison(comparison) {
    if (!comparison || comparison.recommended !== 'reroll') return '';
    const score = Number(comparison.record_score);
    const gap = Number(comparison.gap);
    if (!comparison.record_target || !Number.isFinite(score) || !Number.isFinite(gap)) return '';
    const metric = comparison.comparison === 'expected_final_score' ? '기대 최종점수' : '평가';
    const result = gap > 0.01
        ? `재굴림이 ${metric} +${gap.toFixed(2)}`
        : gap < -0.01
            ? `지금 기록이 ${metric} +${Math.abs(gap).toFixed(2)}`
            : '두 선택이 거의 동률';
    return `
        <div class="ai-action-comparison">
            <span>선택 비교</span>
            <strong>지금 ${escapeHtml(comparison.record_target)} ${score}점 기록 ↔ ${escapeHtml(result)}</strong>
        </div>
    `;
}

function renderDecisionReport(report, expanded) {
    if (!report || typeof report !== 'object') return '';
    const method = report.method || {};
    const state = report.state || {};
    
    const displayLabel = METHOD_LABEL_MAP[method.label] || method.label;
    const methodChip = displayLabel
        ? `<span class="ai-report-chip">${escapeHtml(displayLabel)}</span>`
        : '';
        
    const isExactSource = method.source === 'exact' || method.source === 'exact_value_optimal';
    let confidenceLabel = method.confidence_text;
    if (confidenceLabel === '계산 확정') {
        confidenceLabel = '정밀 계산 완료';
    } else if (confidenceLabel && !isExactSource) {
        confidenceLabel = `확신 ${confidenceLabel}`;
    }
    const confidenceChip = confidenceLabel
        ? `<span class="ai-report-chip">${escapeHtml(confidenceLabel)}</span>`
        : '';
        
    const marginChip = method.decision_margin_text && method.decision_margin_key !== 'unknown'
        ? `<span class="ai-report-chip">${escapeHtml(method.decision_margin_text)}</span>`
        : '';
    const stateChip = expanded && Number.isFinite(Number(state.open_slots))
        ? `<span class="ai-report-chip">열린 칸 ${escapeHtml(state.open_slots)}</span>`
        : '';
        
    // 접혀 있을 때는 중복 텍스트를 숨겨 피로도를 낮추고, 펼쳤을 때만 보여줍니다.
    const whyItems = expanded && Array.isArray(report.why)
        ? report.why.slice(0, 3).map(cleanEvText)
        : [];
    const tradeoffs = expanded && Array.isArray(report.tradeoffs)
        ? report.tradeoffs.slice(0, 2).map(cleanEvText)
        : [];
        
    const rawNote = report.learning_note;
    const cleanNote = LEARNING_NOTE_MAP[rawNote] || cleanEvText(rawNote);
    const note = expanded && cleanNote
        ? `<div class="ai-report-note">${escapeHtml(cleanNote)}</div>`
        : '';
        
    const rawMethodNote = method.note;
    const cleanMethodNote = METHOD_NOTE_MAP[rawMethodNote] || cleanEvText(rawMethodNote);
    const methodNote = expanded && cleanMethodNote
        ? `<div class="ai-report-method">${escapeHtml(cleanMethodNote)}</div>`
        : '';
        
    const tradeoffBlock = tradeoffs.length > 0
        ? `<div class="ai-report-tradeoffs"><div class="ai-report-subtitle">비교 포인트</div>${renderAiReportList(tradeoffs, 'ai-report-list compact')}</div>`
        : '';
        
    const displayConclusion = cleanEvText(report.conclusion || '추천을 계산했습니다.');

    return `
        <div class="ai-report-card">
            <div class="ai-report-title">${escapeHtml(report.title || 'AI 결론 리포트')}</div>
            <div class="ai-report-chips">${methodChip}${confidenceChip}${marginChip}${stateChip}</div>
            <div class="ai-report-conclusion">${escapeHtml(displayConclusion)}</div>
            ${renderProbabilityContext(report.probability_context)}
            ${expanded ? renderAiReportList(whyItems) : ''}
            ${tradeoffBlock}
            ${methodNote}
            ${expanded && method.decision_margin_note ? `<div class="ai-report-method">${escapeHtml(method.decision_margin_note)}</div>` : ''}
            ${note}
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
    const breakdownRows = Array.isArray(aiRec?.breakdown) ? aiRec.breakdown : [];
    const hasReport = Boolean(aiRec?.decision_report);
    if (!aiRec || (breakdownRows.length === 0 && !hasReport)) {
        root.innerHTML = '<div style="color:#999; text-align:center; padding:12px; font-size:0.9em;">대기 중...</div>';
        return;
    }

    const isScoreStage = aiRec?.stage === 'score';
    const expanded = isAiPanelExpanded();
    const visibleCount = expanded ? 5 : 2;
    const rowsToShow = breakdownRows.slice(0, visibleCount);
    const hiddenCount = Math.max(0, Math.min(breakdownRows.length, 5) - rowsToShow.length);
    const summary = aiRec.summary ? `<div class="ai-summary-line">${escapeHtml(aiRec.summary)}</div>` : '';
    const perspective = options.perspective ? `<div class="ai-perspective">${escapeHtml(options.perspective)}</div>` : '';
    const safeTargetId = String(targetId).replace(/'/g, "\\'");
    const reportHasDetails = hasReport && (
        aiRec.decision_report?.learning_note
        || aiRec.decision_report?.method?.note
        || (Array.isArray(aiRec.decision_report?.tradeoffs) && aiRec.decision_report.tradeoffs.length > 0)
    );
    const shouldShowToggle = breakdownRows.length > 2 || reportHasDetails;
    const toggleLabel = expanded ? '간단히 보기' : (hiddenCount > 0 ? `상세 +${hiddenCount}` : '자세히');
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
                    ${renderActionComparison(aiRec.action_comparison)}
                </div>
                <div class="ai-meta-row">
                    <span class="ai-meta-chip">${escapeHtml(getAiStageLabel(aiRec))}</span>
                    <span class="ai-meta-chip">${escapeHtml(getAiModeLabel(aiRec))}</span>
                </div>
            </div>
            ${renderDecisionReport(aiRec.decision_report, expanded)}
            <div class="ai-breakdown-grid">
                ${rows}
            </div>
            ${moreNote}
        </div>
    `;
}
