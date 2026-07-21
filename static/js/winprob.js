/**
 * Exact scorecard projection + cached Monte Carlo win probability UI.
 */

const WinProbabilityPanel = (() => {
    const FAST_SAMPLES = 30;
    const REFINED_SAMPLES = 100;
    const cache = new Map();
    const pending = new Map();
    const histories = new Map();
    let activeStateKey = '';

    function requestKey(payload) {
        return JSON.stringify(payload);
    }

    function stateKey(payload) {
        const normalized = {...payload};
        delete normalized.samples;
        return requestKey(normalized);
    }

    function stagePayload(payload, samples) {
        return {...payload, samples};
    }

    function clampProbability(value) {
        return Math.max(0.03, Math.min(0.97, Number(value)));
    }

    function updateHistory(targetId, probability) {
        const history = histories.get(targetId) || [];
        const point = clampProbability(probability);
        const previous = history[history.length - 1];
        if (typeof previous === 'number' && Math.abs(previous - point) < 0.003) return history;
        const updated = history.concat(point).slice(-28);
        histories.set(targetId, updated);
        return updated;
    }

    function graphMarkup(history) {
        if (!Array.isArray(history) || history.length < 2) return '';
        const width = 260;
        const height = 96;
        const step = width / (history.length - 1);
        const points = history.map((value, index) => {
            const x = (index * step).toFixed(1);
            const y = ((1 - value) * (height - 12) + 6).toFixed(1);
            return `${x},${y}`;
        }).join(' ');
        return `
            <svg viewBox="0 0 ${width} ${height}" class="winprob-graph" preserveAspectRatio="none" aria-hidden="true">
                <line x1="0" y1="${height / 2}" x2="${width}" y2="${height / 2}" stroke="rgba(255,255,255,0.12)" stroke-dasharray="4 4"></line>
                <polyline fill="none" stroke="var(--mint-strong)" stroke-width="3" points="${points}"></polyline>
            </svg>`;
    }

    function render(targetId, result, options = {}) {
        const root = document.getElementById(targetId);
        if (!root) return;
        const leftLabel = escapeHtml(options.leftLabel || '나');
        const rightLabel = escapeHtml(options.rightLabel || '상대');
        const myProjected = Number(result?.my_projected);
        const oppProjected = Number(result?.opp_projected);
        const hasProjection = Number.isFinite(myProjected) && Number.isFinite(oppProjected);

        if (!options.readyToCompare) {
            root.innerHTML = `
                <div class="winprob-head">
                    <div class="winprob-title">판세 분석</div>
                    <div class="winprob-sub">상대 입장 후 최적 플레이 기준 승률을 계산합니다</div>
                </div>`;
            return;
        }

        if (!result || result.status === 'pending') {
            const projection = hasProjection
                ? `<div class="winprob-meta">이대로 진행하면 예상되는 최종 점수 · ${leftLabel} ${myProjected.toFixed(1)} / ${rightLabel} ${oppProjected.toFixed(1)}</div>`
                : '';
            root.innerHTML = `
                <div class="winprob-head">
                    <div class="winprob-title">최적 플레이 기준 승률</div>
                    <div class="winprob-sub">현재 주사위와 남은 굴림까지 반영해 시뮬레이션 중</div>
                </div>
                ${projection}
                <div class="winprob-loading" role="status">승률 계산 중...</div>`;
            return;
        }

        if (result.status === 'error') {
            root.innerHTML = `
                <div class="winprob-head">
                    <div class="winprob-title">판세 분석</div>
                    <div class="winprob-sub">승률 계산을 잠시 사용할 수 없습니다</div>
                </div>`;
            return;
        }

        const myProbability = clampProbability(result.effective_win_rate);
        const myPct = Math.round(myProbability * 100);
        const oppPct = 100 - myPct;
        const history = options.refining
            ? (histories.get(targetId) || [])
            : updateHistory(targetId, myProbability);
        const margin = Math.round(Number(result.confidence_95 || 0) * 100);
        const samples = Number(result.samples || 0);
        const sampleLabel = samples >= REFINED_SAMPLES
            ? `${samples}회 정밀 추정`
            : `${samples}회 빠른 추정`;
        const refinement = options.refining
            ? ` → ${REFINED_SAMPLES}회 정밀 계산 중`
            : '';
        root.innerHTML = `
            <div class="winprob-head">
                <div class="winprob-title">최적 플레이 기준 승률</div>
                <div class="winprob-sub">${sampleLabel}${refinement} · 표본 오차 약 ±${margin}%p</div>
            </div>
            <div class="winprob-bar" role="img" aria-label="${leftLabel} ${myPct}%, ${rightLabel} ${oppPct}%">
                <div class="winprob-left" style="width:${myPct}%">${leftLabel} ${myPct}%</div>
                <div class="winprob-right" style="width:${oppPct}%">${rightLabel} ${oppPct}%</div>
            </div>
            <div class="winprob-meta">이대로 진행하면 예상되는 최종 점수 · ${leftLabel} ${myProjected.toFixed(1)} / ${rightLabel} ${oppProjected.toFixed(1)}</div>
            ${graphMarkup(history)}
        `;
    }

    async function fetchStage(targetId, basePayload, payload, options, currentStateKey, key) {
        try {
            const response = await fetch('/api/win-probability', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                cache: 'no-store',
                body: JSON.stringify(payload),
            });
            const result = await response.json();
            if (!response.ok && response.status !== 202) throw new Error(result.error || `HTTP ${response.status}`);
            if (result.status === 'pending') {
                result._retryAt = Date.now() + Math.max(500, Math.min(Number(result.retry_after_ms || 900), 2000));
            }
            cache.set(key, result);
            while (cache.size > 64) cache.delete(cache.keys().next().value);
            if (activeStateKey === currentStateKey) {
                request(targetId, basePayload, options);
            }
            if (result.status === 'pending' && activeStateKey === currentStateKey) {
                const retryMs = Math.max(500, Math.min(Number(result.retry_after_ms || 900), 2000));
                window.setTimeout(
                    () => ensureStage(targetId, basePayload, payload, options, currentStateKey, true),
                    retryMs,
                );
            }
        } catch (error) {
            cache.set(key, {status: 'error'});
            if (activeStateKey === currentStateKey) request(targetId, basePayload, options);
            console.warn('win probability failed', error);
        } finally {
            pending.delete(key);
        }
    }

    function ensureStage(targetId, basePayload, payload, options, currentStateKey, force = false) {
        if (activeStateKey !== currentStateKey) return;
        const key = requestKey(payload);
        const cached = cache.get(key);
        const waitingForRetry = cached?.status === 'pending'
            && Date.now() < Number(cached._retryAt || 0);
        if (pending.has(key)) return;
        if (!force && (cached?.status === 'ready' || cached?.status === 'error' || waitingForRetry)) return;
        pending.set(
            key,
            fetchStage(targetId, basePayload, payload, options, currentStateKey, key),
        );
    }

    function request(targetId, payload, options = {}) {
        if (!options.readyToCompare) {
            activeStateKey = '';
            render(targetId, null, options);
            return;
        }
        const basePayload = {...payload};
        delete basePayload.samples;
        const currentStateKey = stateKey(basePayload);
        activeStateKey = currentStateKey;

        const fastPayload = stagePayload(basePayload, FAST_SAMPLES);
        const refinedPayload = stagePayload(basePayload, REFINED_SAMPLES);
        const fastResult = cache.get(requestKey(fastPayload));
        const refinedResult = cache.get(requestKey(refinedPayload));

        if (refinedResult?.status === 'ready') {
            render(targetId, refinedResult, options);
            return;
        }
        if (fastResult?.status === 'ready') {
            render(targetId, fastResult, {
                ...options,
                refining: refinedResult?.status !== 'error',
            });
            if (refinedResult?.status !== 'error') {
                ensureStage(targetId, basePayload, refinedPayload, options, currentStateKey);
            }
            return;
        }
        if (fastResult?.status === 'error') {
            render(targetId, fastResult, options);
            return;
        }

        render(targetId, fastResult || {status: 'pending'}, options);
        ensureStage(targetId, basePayload, fastPayload, options, currentStateKey);
    }

    return {request, render};
})();
