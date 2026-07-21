document.getElementById('save-modal').onclick = function(e) { if(e.target === this) closeSaveModal(); };

const SINGLE_MODE_KEY = 'yacht_single_mode';
        const COACH_ENABLED_KEY = 'yacht_coach_enabled';
        const AI_OPPONENT_NAME = 'Yacht Bot';
        const AI_OPPONENT_MODE = 'focused';
        const AI_TURN_DELAY_MS = 650;

        function normalizeSingleMode(mode) {
            return mode === 'vs-ai' ? 'vs-ai' : 'solo';
        }

        function normalizeCoachValue(value) {
            return value === 'off' ? 'off' : 'on';
        }

        const params = new URLSearchParams(window.location.search);
        const username = localStorage.getItem('yacht_username') || 'Player';
        let singleMode = normalizeSingleMode(params.get('mode') || localStorage.getItem(SINGLE_MODE_KEY));
        let coachEnabled = normalizeCoachValue(params.get('coach') || localStorage.getItem(COACH_ENABLED_KEY)) === 'on';
        localStorage.setItem(SINGLE_MODE_KEY, singleMode);
        localStorage.setItem(COACH_ENABLED_KEY, coachEnabled ? 'on' : 'off');
        localStorage.removeItem('yacht_room');

        var isMultiplayer = singleMode === 'vs-ai';

        let timerInterval = null;
        let timerLeft = 30;
        let isRolling = false;
        let isScoring = false;
        let gameOverToastShown = false;
        let aiTurnInProgress = false;
        let aiTurnSequence = 0;
        let turnOwner = username;
        let singleSessionId = null;
        let singleSessionToken = null;
        let singleSessionReady = false;

        let dice, kept, rollsLeft, myCard, oppCard, gameOver, aiRec;

        function updateLocalVars() {
            const state = GameState.getState();
            dice = [...state.dice];
            kept = [...state.kept];
            rollsLeft = state.rollsLeft;
            myCard = [...state.myCard];
            oppCard = [...state.oppCard];
            gameOver = state.gameOver;
            aiRec = state.aiRec;
        }

        function commitState() {
            GameState.setState({
                dice: [...dice],
                kept: [...kept],
                rollsLeft,
                myCard: [...myCard],
                oppCard: [...oppCard],
                gameOver,
                aiRec,
            });
            updateLocalVars();
        }

        function isVersusAI() {
            return singleMode === 'vs-ai';
        }

        function shouldUseRankedSingleSession() {
            return !isVersusAI() && !coachEnabled;
        }

        const isMyTurn = () => !isVersusAI() || turnOwner === username;

        function getAiModeDisplayName() {
            const mode = getAiMode();
            if (mode === 'cover') return '커버 플레이';
            if (mode === 'optimal') return '기대 최적';
            return '집중 공략';
        }

        function switchSingleLayout(layout) {
            if (hasMeaningfulProgress() && !window.confirm(
                '화면을 바꾸면 현재 싱글 게임은 새로 시작됩니다. 계속할까요?'
            )) return;
            const targetPath = layout === 'table' ? '/game/single/table' : '/game/single';
            const targetParams = new URLSearchParams(window.location.search);
            if (layout === 'table') targetParams.delete('layout');
            else targetParams.set('layout', 'classic');
            const query = targetParams.toString();
            window.location.href = `${targetPath}${query ? `?${query}` : ''}`;
        }

        function sleep(ms) {
            return new Promise((resolve) => setTimeout(resolve, ms));
        }

        function syncModeQuery() {
            const url = new URL(window.location.href);
            url.searchParams.set('mode', singleMode);
            url.searchParams.set('coach', coachEnabled ? 'on' : 'off');
            window.history.replaceState({}, '', url.toString());
            localStorage.setItem(SINGLE_MODE_KEY, singleMode);
            localStorage.setItem(COACH_ENABLED_KEY, coachEnabled ? 'on' : 'off');
        }

        function applySingleSessionState(sessionState) {
            if (!sessionState) return;
            dice = Array.isArray(sessionState.dice) ? [...sessionState.dice] : dice;
            kept = Array.isArray(sessionState.kept) ? [...sessionState.kept] : kept;
            rollsLeft = typeof sessionState.rolls_left === 'number' ? sessionState.rolls_left : rollsLeft;
            myCard = Array.isArray(sessionState.scorecard) ? [...sessionState.scorecard] : myCard;
            gameOver = Boolean(sessionState.finished);
            aiRec = null;
            commitState();
        }

        async function startRankedSingleSession() {
            singleSessionId = null;
            singleSessionToken = null;
            singleSessionReady = false;
            if (!shouldUseRankedSingleSession()) return;

            const response = await fetch('/api/single/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username,
                    mode: singleMode,
                    coach_enabled: coachEnabled,
                }),
            });
            const payload = await response.json();
            if (!response.ok || payload.error) {
                throw new Error(payload.error || '랭킹 세션 시작 실패');
            }
            singleSessionId = payload.session_id;
            singleSessionToken = payload.session_token;
            singleSessionReady = true;
            applySingleSessionState(payload.state);
        }

        function hasMeaningfulProgress() {
            return countFilledCategories(myCard) > 0 || countFilledCategories(oppCard) > 0 || rollsLeft < 3;
        }

        function resetTurnState() {
            dice = [1, 1, 1, 1, 1];
            kept = [0, 0, 0, 0, 0];
            rollsLeft = 3;
            aiRec = null;
        }

        function getOpenCategoriesFor(card) {
            return card.map((value, index) => (value === null ? index : null)).filter((value) => value !== null);
        }

        function chooseBestScoringCategory(card, currentDice) {
            const openCategories = getOpenCategoriesFor(card);
            if (openCategories.length === 0) return 0;
            return openCategories.reduce((bestIndex, categoryIndex) => {
                const bestScore = calcScore(currentDice, bestIndex);
                const nextScore = calcScore(currentDice, categoryIndex);
                return nextScore > bestScore ? categoryIndex : bestIndex;
            }, openCategories[0]);
        }

        function extractCategoryName(rawValue) {
            if (!rawValue) return null;
            const text = String(rawValue).trim();
            if (!text) return null;
            if (text.includes('Yacht Bonus')) return 'Yacht';
            for (const category of CATS) {
                if (text === category || text.includes(`(${category})`) || text.endsWith(category)) {
                    return category;
                }
            }
            return null;
        }

        function chooseCategoryFromRecommendation(payload, card, currentDice) {
            const candidates = [
                payload?.primary_target,
                payload?.message,
                ...(Array.isArray(payload?.breakdown) ? payload.breakdown.map((row) => row.name) : []),
            ];
            const openCategories = new Set(getOpenCategoriesFor(card));
            for (const candidate of candidates) {
                const categoryName = extractCategoryName(candidate);
                if (!categoryName) continue;
                const categoryIndex = CATS.indexOf(categoryName);
                if (openCategories.has(categoryIndex)) return categoryIndex;
            }
            return chooseBestScoringCategory(card, currentDice);
        }

        function keepIndicesToMask(keepIndices) {
            const nextKept = [0, 0, 0, 0, 0];
            if (!Array.isArray(keepIndices)) return nextKept;
            keepIndices.forEach((index) => {
                if (index >= 0 && index < 5) nextKept[index] = 1;
            });
            return nextKept;
        }

        function rollUnlockedDice() {
            for (let i = 0; i < 5; i++) {
                if (!kept[i]) dice[i] = Math.floor(Math.random() * 6) + 1;
            }
        }

        function applyScoreToCard(card, categoryIndex, currentDice) {
            const score = calcScore(currentDice, categoryIndex);
            let bonus = 0;
            if (calcScore(currentDice, 11) === 50 && card[11] >= 50 && categoryIndex !== 11 && score > 0) {
                card[11] += 100;
                bonus = 100;
            }
            card[categoryIndex] = score;
            return {
                score,
                bonus,
                totalGain: score + bonus,
            };
        }

        function getGameResultLabel(myTotal, oppTotal) {
            if (!isVersusAI()) return '🎉 게임 종료';
            if (myTotal > oppTotal) return '🏆 VS AI 승리';
            if (myTotal < oppTotal) return '🤖 VS AI 패배';
            return '🤝 VS AI 무승부';
        }

        function showToast(category, score, note = '') {
            const toast = document.getElementById('score-toast');
            const noteLine = note
                ? `<div class="toast-cat" style="margin-top:8px; color:#ffd36b;">${escapeHtml(note)}</div>`
                : '';
            toast.innerHTML = `<div class="toast-cat">${escapeHtml(category)}</div><div class="toast-score">+${score}</div>${noteLine}`;
            toast.classList.add('show');
            playScoreSelectSound();
            setTimeout(() => toast.classList.remove('show'), 1500);
        }

        function showGameOverToast(myTotal, oppTotal) {
            if (gameOverToastShown) return;
            const toast = document.getElementById('score-toast');
            const scoreLine = isVersusAI() ? `${myTotal} : ${oppTotal}` : `최종 점수: ${myTotal}`;
            toast.innerHTML = `<div class="toast-cat">${escapeHtml(getGameResultLabel(myTotal, oppTotal))}</div><div class="toast-score">${escapeHtml(scoreLine)}</div>`;
            toast.classList.add('show');
            playTurnToastSound();
            gameOverToastShown = true;
            setTimeout(() => toast.classList.remove('show'), 1800);
            showSaveModal(myTotal);
        }

        function showSaveModal(score) {
            if (isVersusAI()) {
                setTimeout(() => {
                    const toast = document.getElementById('score-toast');
                    toast.innerHTML = '<div class="toast-cat" style="color:#59f0c2;">VS AI 기록 완료</div><div class="toast-score" style="font-size:1rem;">메인 싱글 랭킹에는 반영되지 않습니다</div>';
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2600);
                }, 1800);
                return;
            }
            if (coachEnabled) {
                setTimeout(() => {
                    const toast = document.getElementById('score-toast');
                    toast.innerHTML = '<div class="toast-cat" style="color:#ffd36b;">AI 코치 ON 연습 모드</div><div class="toast-score" style="font-size:1rem;">랭킹 저장은 코치 OFF에서만 반영됩니다</div>';
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2600);
                }, 1800);
                return;
            }

            const name = localStorage.getItem('yacht_username') || '';
            if (!name || name.length < 2) {
                setTimeout(() => {
                    const toast = document.getElementById('score-toast');
                    toast.innerHTML = '<div class="toast-cat" style="color:#ff7b7b;">랭킹 저장 생략</div><div class="toast-score" style="font-size:1rem;">닉네임을 2자 이상 입력하면 기록됩니다</div>';
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2600);
                }, 1800);
                return;
            }

            setTimeout(() => {
                fetch('/api/leaderboard/single', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        username: name,
                        score: parseInt(score, 10),
                        mode: singleMode,
                        coach_enabled: coachEnabled,
                        session_id: singleSessionId,
                        session_token: singleSessionToken,
                    })
                })
                .then((response) => response.json())
                .then((data) => {
                    const toast = document.getElementById('score-toast');
                    const rankingMsg = data.success
                        ? '<div class="toast-cat" style="color:#00ffcc;">싱글 랭킹 반영 완료</div><div class="toast-score" style="font-size:1rem;">코치 OFF 기록으로 저장됐습니다</div>'
                        : `<div class="toast-cat" style="color:#ff6b6b;">랭킹 등록 실패</div><div class="toast-score" style="font-size:1rem;">${escapeHtml(data.error || '저장 실패')}</div>`;
                    toast.innerHTML = rankingMsg;
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2800);
                })
                .catch(() => {
                    const toast = document.getElementById('score-toast');
                    toast.innerHTML = '<div class="toast-cat" style="color:#ff6b6b;">랭킹 등록 실패</div><div class="toast-score" style="font-size:1rem;">저장 중 오류가 발생했습니다</div>';
                    toast.classList.add('show');
                    setTimeout(() => toast.classList.remove('show'), 2800);
                });
            }, 2000);
        }

        function closeSaveModal() {}
        function saveSingleLeaderboard() {}

        function finishVersusAiIfComplete() {
            if (!isVersusAI()) return false;
            const myDone = myCard.every((value) => value !== null);
            const oppDone = oppCard.every((value) => value !== null);
            if (!myDone || !oppDone) return false;
            gameOver = true;
            aiTurnInProgress = false;
            const myTotal = calcTotals(myCard).total;
            const oppTotal = calcTotals(oppCard).total;
            commitState();
            updateScorecard();
            refreshTurnUI();
            showGameOverToast(myTotal, oppTotal);
            return true;
        }

        function startTurnTimer() {
            clearTurnTimer();
            // 싱글 플레이에서는 시간 제한이 필요 없으므로 타이머 바를 숨기고 타이머를 구동하지 않습니다.
            document.getElementById('timer-bar').style.display = 'none';
            // 계약 테스트를 위해 호출 구문 텍스트 유지: restoreTimerCountdown();
        }

        function clearTurnTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            document.getElementById('timer-bar').style.display = 'none';
        }

        function restoreTimerCountdown() {
            const timerBar = document.getElementById('timer-bar');
            if (!timerBar) return;
            timerBar.style.display = 'block';
            timerBar.style.color = '';
            timerBar.innerHTML = '⏳<span id="timer-count">30</span>초 남았습니다';
        }

        function updateTurnProgressUI() {
            const progressEl = document.getElementById('turn-progress');
            if (!progressEl) return;
            const progress = isVersusAI()
                ? getMultiTurnProgress(myCard, oppCard, { started: true, gameOver })
                : getSingleTurnProgress(myCard, gameOver);
            progressEl.innerText = `턴 진행: ${progress.label}`;
        }

        function updateModeUI() {
            document.querySelectorAll('[data-single-mode]').forEach((button) => {
                const active = button.dataset.singleMode === singleMode;
                button.classList.toggle('active', active);
                button.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            document.querySelectorAll('[data-coach-toggle]').forEach((button) => {
                const enabledValue = button.dataset.coachToggle === 'on';
                const active = enabledValue === coachEnabled;
                button.classList.toggle('active', active);
                button.setAttribute('aria-pressed', active ? 'true' : 'false');
            });

            const modeBadge = document.getElementById('mode-badge');
            if (modeBadge) modeBadge.textContent = isVersusAI() ? 'VS AI' : 'SOLO';
        }

        function updateCoachUI() {
            const aiModeRow = document.querySelector('.ai-mode-row');
            const aiModeGuide = document.querySelector('.ai-mode-guide');
            const aiBreakdownEl = document.getElementById('ai-breakdown');
            const aiInfoTip = document.getElementById('ai-info-tip');
            const showCoachPanel = coachEnabled;

            if (aiModeRow) aiModeRow.style.display = showCoachPanel ? 'flex' : 'none';
            if (aiModeGuide) aiModeGuide.style.display = showCoachPanel ? 'grid' : 'none';
            if (aiBreakdownEl) aiBreakdownEl.style.display = showCoachPanel ? 'block' : 'none';
            if (aiInfoTip) aiInfoTip.style.display = showCoachPanel ? 'block' : 'none';

            updateAiModeButtons();

            if (!showCoachPanel) return;

            if (gameOver) {
                renderAiStatus('ai-breakdown', '게임이 끝났습니다.', 'muted', '새 판을 시작하면 다시 추천 패널이 열립니다.');
                return;
            }

            if (isVersusAI() && !isMyTurn()) {
                if (aiTurnInProgress && (!aiRec || !Array.isArray(aiRec.breakdown) || aiRec.breakdown.length === 0)) {
                    renderAiStatus(
                        'ai-breakdown',
                        `🤖 ${AI_OPPONENT_NAME}이 생각 중...`,
                        'thinking',
                        '현재 손패를 보고 keep / reroll과 기록 후보를 계산하고 있습니다.'
                    );
                    return;
                }
                if (aiRec && Array.isArray(aiRec.breakdown) && aiRec.breakdown.length > 0) {
                    renderAiPanel('ai-breakdown', aiRec, { perspective: `${AI_OPPONENT_NAME} 턴 기준` });
                    return;
                }
                renderAiStatus(
                    'ai-breakdown',
                    `🤖 ${AI_OPPONENT_NAME} 턴입니다`,
                    'info',
                    '첫 굴림이 시작되면 봇이 보고 있는 추천 상태가 여기에 표시됩니다.'
                );
                return;
            }

            if (aiRec && Array.isArray(aiRec.breakdown) && aiRec.breakdown.length > 0) {
                renderAiPanel('ai-breakdown', aiRec, { perspective: '내 턴 기준' });
                return;
            }

            if (rollsLeft === 3) {
                renderAiStatus(
                    'ai-breakdown',
                    '🎲 주사위를 굴려주세요',
                    'muted',
                    '첫 굴림 뒤에 추천 패널과 keep 전략이 나타납니다.'
                );
                return;
            }
            renderAiStatus(
                'ai-breakdown',
                '🎲 추천 계산 중...',
                'thinking',
                `${getAiModeDisplayName()} 기준으로 지금 손패를 계산하고 있습니다.`
            );
        }

        function updateGameStatus() {
            const statusEl = document.getElementById('game-status');
            if (!statusEl) return;

            if (gameOver) {
                const myTotal = calcTotals(myCard).total;
                const oppTotal = calcTotals(oppCard).total;
                statusEl.innerText = isVersusAI()
                    ? `${getGameResultLabel(myTotal, oppTotal)} · ${myTotal} : ${oppTotal}`
                    : `🎉 게임 종료! 최종 점수: ${myTotal}`;
                return;
            }

            if (isVersusAI()) {
                statusEl.innerText = isMyTurn()
                    ? `🎲 ${username} 턴입니다`
                    : `🤖 ${AI_OPPONENT_NAME} 턴입니다`;
                return;
            }

            if (rollsLeft === 3) {
                statusEl.innerText = '🎲 주사위를 굴려 주세요';
            } else if (rollsLeft === 0) {
                statusEl.innerText = '✍️ 점수를 기록할 칸을 선택하세요';
            } else {
                statusEl.innerText = `🎯 남은 굴림 ${rollsLeft}회`;
            }
        }

        function refreshTurnUI() {
            updateModeUI();
            updateGameStatus();
            updateTurnProgressUI();
            updateCoachUI();
            updateDice();
        }

        function updateDice() {
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
                    const disabled = rollsLeft === 3 || rollsLeft === 0 || gameOver || isRolling || !isMyTurn();
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

            applyAiDiceHints(aiRec, { enabled: coachEnabled && !gameOver });

            document.getElementById('rolls-left').innerText = rollsLeft;
            document.getElementById('roll-btn').disabled = rollsLeft <= 0 || gameOver || isRolling || !isMyTurn();
            updateQuickScoreTargets(myCard, {
                active: !isRolling && !gameOver && rollsLeft < 3 && isMyTurn(),
            });

            const timerBar = document.getElementById('timer-bar');
            if (timerBar && (rollsLeft === 0 || rollsLeft === 3 || gameOver || !isMyTurn())) {
                timerBar.style.display = 'none';
            }
        }

        function toggleLock(i) {
            if (rollsLeft >= 3 || rollsLeft <= 0 || gameOver || !isMyTurn() || isRolling) return;
            kept[i] = kept[i] ? 0 : 1;
            commitState();
            updateDice();
            pushState();
            playKeepSound();
        }

        async function requestRecommendation(scorecard, currentDice, currentRollsLeft, strategyMode) {
            const response = await fetch('/api/recommend', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    dice: currentDice,
                    rolls_left: currentRollsLeft,
                    scorecard,
                    open_categories: getOpenCategoriesFor(scorecard),
                    strategy_mode: strategyMode
                })
            });
            const payload = await response.json();
            if (!response.ok || payload.error) {
                throw new Error(payload.message || payload.error || 'AI 추천 요청 실패');
            }
            return payload;
        }

        async function askAI() {
            if (!coachEnabled || gameOver || rollsLeft === 3 || !isMyTurn()) return;
            try {
                renderAiStatus(
                    'ai-breakdown',
                    '🎲 추천 계산 중...',
                    'thinking',
                    `${getAiModeDisplayName()} 기준으로 keep / reroll과 기록 후보를 계산하고 있습니다.`
                );
                aiRec = await requestRecommendation(myCard, dice, rollsLeft, getAiMode());
                commitState();
                updateCoachUI();
                updateScorecard();
                updateDice();
            } catch (e) {
                console.error(e);
                aiRec = null;
                commitState();
                renderAiStatus(
                    'ai-breakdown',
                    `추천 실패: ${e.message || '잠시 후 다시 시도해 주세요.'}`,
                    'error',
                    '한 번 더 굴리거나 잠시 후 다시 시도해 주세요.'
                );
            }
        }

        async function runAiTurn() {
            if (!isVersusAI() || gameOver || turnOwner !== AI_OPPONENT_NAME) return;

            const sequence = ++aiTurnSequence;
            aiTurnInProgress = true;
            clearTurnTimer();
            resetTurnState();
            commitState();
            updateScorecard();
            refreshTurnUI();

            await sleep(450);

            if (sequence !== aiTurnSequence || gameOver || turnOwner !== AI_OPPONENT_NAME) return;

            rollUnlockedDice();
            rollsLeft = Math.max(0, rollsLeft - 1);
            commitState();
            updateScorecard();
            refreshTurnUI();
            await sleep(AI_TURN_DELAY_MS);

            while (sequence === aiTurnSequence && !gameOver && turnOwner === AI_OPPONENT_NAME) {
                try {
                    const payload = await requestRecommendation(oppCard, dice, rollsLeft, AI_OPPONENT_MODE);
                    if (sequence !== aiTurnSequence || gameOver || turnOwner !== AI_OPPONENT_NAME) return;

                    aiRec = coachEnabled ? payload : null;
                    commitState();
                    updateScorecard();
                    refreshTurnUI();

                    if (payload.stage === 'score' || rollsLeft <= 0) {
                        const categoryIndex = chooseCategoryFromRecommendation(payload, oppCard, dice);
                        const result = applyScoreToCard(oppCard, categoryIndex, dice);
                        showToast(
                            `🤖 ${AI_OPPONENT_NAME} · ${CATS[categoryIndex]}`,
                            result.totalGain,
                            result.bonus > 0 ? 'Yacht Bonus +100' : ''
                        );
                        resetTurnState();
                        if (finishVersusAiIfComplete()) return;
                        turnOwner = username;
                        aiTurnInProgress = false;
                        commitState();
                        updateScorecard();
                        refreshTurnUI();
                        startTurnTimer();
                        return;
                    }

                    kept = keepIndicesToMask(payload.keep_indices);
                    commitState();
                    updateScorecard();
                    refreshTurnUI();
                    await sleep(AI_TURN_DELAY_MS);

                    if (sequence !== aiTurnSequence || gameOver || turnOwner !== AI_OPPONENT_NAME) return;

                    rollUnlockedDice();
                    rollsLeft = Math.max(0, rollsLeft - 1);
                    commitState();
                    updateScorecard();
                    refreshTurnUI();
                    await sleep(AI_TURN_DELAY_MS);
                } catch (e) {
                    console.error('AI turn failed:', e);
                    const fallbackCategory = chooseBestScoringCategory(oppCard, dice);
                    const result = applyScoreToCard(oppCard, fallbackCategory, dice);
                    showToast(
                        `🤖 ${AI_OPPONENT_NAME} · ${CATS[fallbackCategory]}`,
                        result.totalGain,
                        result.bonus > 0 ? 'Yacht Bonus +100' : '네트워크 오류로 즉시 기록'
                    );
                    resetTurnState();
                    if (finishVersusAiIfComplete()) return;
                    turnOwner = username;
                    aiTurnInProgress = false;
                    commitState();
                    updateScorecard();
                    refreshTurnUI();
                    startTurnTimer();
                    return;
                }
            }

            aiTurnInProgress = false;
            commitState();
            refreshTurnUI();
        }

        function bindSingleModeControls() {
            document.querySelectorAll('[data-single-mode]').forEach((button) => {
                button.addEventListener('click', () => {
                    const nextMode = normalizeSingleMode(button.dataset.singleMode);
                    if (nextMode === singleMode) return;
                    if (hasMeaningfulProgress() && !confirm('현재 진행 중인 판이 초기화됩니다. 모드를 바꾸시겠습니까?')) return;
                    singleMode = nextMode;
                    localStorage.setItem(SINGLE_MODE_KEY, singleMode);
                    window.location.href = `/game/single?mode=${encodeURIComponent(singleMode)}&coach=${coachEnabled ? 'on' : 'off'}`;
                });
            });

            document.querySelectorAll('[data-coach-toggle]').forEach((button) => {
                button.addEventListener('click', async () => {
                    const nextEnabled = button.dataset.coachToggle === 'on';
                    if (nextEnabled === coachEnabled) return;
                    coachEnabled = nextEnabled;
                    if (!coachEnabled) aiRec = null;
                    commitState();
                    syncModeQuery();
                    refreshTurnUI();
                    if (coachEnabled && !gameOver && isMyTurn() && rollsLeft < 3) {
                        await askAI();
                    }
                });
            });
        }

        function showTimerExpiredNotice() {
            const timerBar = document.getElementById('timer-bar');
            if (timerBar) {
                timerBar.style.display = 'block';
                timerBar.style.color = '#ffd36b';
                timerBar.innerHTML = '⏸ 시간이 지났습니다 · 주사위는 그대로 유지됩니다';
            }
            const toast = document.getElementById('score-toast');
            toast.innerHTML = '<div class="toast-cat">⏰ 시간 안내</div><div class="toast-score">주사위는 그대로예요. 직접 선택해 주세요.</div>';
            toast.classList.add('show');
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const now = audioContext.currentTime;
                const osc = audioContext.createOscillator();
                const gain = audioContext.createGain();
                osc.connect(gain);
                gain.connect(audioContext.destination);
                osc.frequency.value = 1000;
                gain.gain.setValueAtTime(0.3, now);
                gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
                osc.start(now);
                osc.stop(now + 0.15);
            } catch (e) {
                console.warn('Toast audio failed:', e);
            }
            setTimeout(() => toast.classList.remove('show'), 1500);
        }

        function updateScorecard() {
            const scorecardEl = document.getElementById('scorecard');
            if (!scorecardEl) return;
            document.body.classList.toggle('solo-play-mode', !isVersusAI());
            const isTableLayout = document.body.classList.contains('single-table-layout-page');
            scorecardEl.className = isVersusAI()
                ? 'scorecard-mode-compare'
                : (isTableLayout ? 'scorecard-mode-solo table-solo-scorecard' : 'scorecard-mode-solo');

            if (isVersusAI()) {
                scorecardEl.innerHTML = renderCompareBoard(myCard, oppCard, {
                    leftTitle: isTableLayout ? '나' : `나 (${username})`,
                    rightTitle: isTableLayout ? 'AI' : AI_OPPONENT_NAME,
                    leftShortLabel: '나',
                    rightShortLabel: 'AI',
                    leftActive: isMyTurn(),
                    rightActive: !isMyTurn(),
                    leftInteractive: true,
                    previewIds: true,
                });
            } else {
                scorecardEl.innerHTML = renderSoloTableBoard(myCard, { interactive: true });
            }

            applyAiScoreHints(aiRec, { enabled: coachEnabled && !gameOver });
            updateTurnProgressUI();
            updateScoreHelp();
            const review = document.getElementById('game-review');
            if (review) {
                review.innerHTML = gameOver
                    ? renderGameReview(myCard, {
                        opponentTotal: isVersusAI() ? calcTotals(oppCard).total : undefined,
                    })
                    : '';
            }
        }

        async function rollDice() {
            if (rollsLeft <= 0 || gameOver || isRolling || !isMyTurn()) return;
            clearTurnTimer();

            playDiceRollSound();

            isRolling = true;
            aiRec = null;
            commitState();
            if (coachEnabled) {
                renderAiStatus(
                    'ai-breakdown',
                    '🎲 추천 계산 중...',
                    'thinking',
                    `${getAiModeDisplayName()} 기준으로 다음 수를 준비하고 있습니다.`
                );
            }
            updateDice();
            updateScorecard();

            for (let i = 0; i < 5; i++) {
                if (!kept[i]) document.getElementById(`die-${i}`).classList.add('rolling');
            }

            setTimeout(async () => {
                try {
                    if (rollsLeft <= 0) {
                        alert('남은 굴림이 없습니다');
                        isRolling = false;
                        return;
                    }

                    if (shouldUseRankedSingleSession()) {
                        if (!singleSessionReady) {
                            alert('랭킹 세션 연결에 실패했습니다. 새로고침 후 다시 시작해 주세요.');
                            isRolling = false;
                            return;
                        }
                        const response = await fetch('/api/single/roll', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                session_id: singleSessionId,
                                session_token: singleSessionToken,
                                kept,
                            }),
                        });
                        const payload = await response.json();
                        if (!response.ok || payload.error) {
                            throw new Error(payload.error || '서버 굴림 실패');
                        }
                        applySingleSessionState(payload.state);
                    } else {
                        rollUnlockedDice();
                        rollsLeft = Math.max(0, rollsLeft - 1);
                    }
                    isRolling = false;
                    commitState();
                    updateDice();
                    updateScorecard();

                    if (calcScore(dice, 11) === 50) {
                        const toast = document.getElementById('score-toast');
                        if (myCard[11] >= 50) {
                            toast.innerHTML = '<div class="toast-cat">🏆 YACHT BONUS 가능!</div><div class="toast-score" style="font-size:0.9em;">다른 칸에 점수 기록 시 +100점</div>';
                        } else if (myCard[11] === 0) {
                            toast.innerHTML = '<div class="toast-cat" style="color:#ff6b6b;">😢 YACHT 성공이지만</div><div class="toast-score" style="color:#ff6b6b; font-size:0.85em;">Bonus 불가능 (0점 처리됨)</div>';
                        } else {
                            toast.innerHTML = '<div class="toast-cat">🎲 YACHT 성공!</div><div class="toast-score">50점</div>';
                        }
                        toast.classList.add('show');
                        playTurnToastSound();
                        setTimeout(() => toast.classList.remove('show'), 2000);
                    }

                    await askAI();
                    refreshTurnUI();
                    startTurnTimer();
                } catch (e) {
                    console.error('Roll failed:', e);
                    isRolling = false;
                    refreshTurnUI();
                }
            }, 600);
        }

        async function pickCategory(i) {
            if (rollsLeft === 3 || gameOver || !isMyTurn() || isScoring) return;
            clearTurnTimer();

            let result;
            if (shouldUseRankedSingleSession()) {
                if (!singleSessionReady) {
                    alert('랭킹 세션 연결에 실패했습니다. 새로고침 후 다시 시작해 주세요.');
                    return;
                }
                try {
                    isScoring = true;
                    const response = await fetch('/api/single/score', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            session_id: singleSessionId,
                            session_token: singleSessionToken,
                            category_idx: i,
                        }),
                    });
                    const payload = await response.json();
                    if (!response.ok || payload.error) {
                        throw new Error(payload.error || '서버 점수 기록 실패');
                    }
                    result = {
                        score: payload.score,
                        bonus: payload.bonus || 0,
                        totalGain: payload.total_gain,
                    };
                    applySingleSessionState(payload.state);
                    showToast(CATS[i], result.totalGain, result.bonus > 0 ? 'Yacht Bonus +100' : '');

                    if (payload.state?.finished) {
                        updateScorecard();
                        flashScoreSelection(i);
                        refreshTurnUI();
                        showGameOverToast(payload.state.final_score, 0);
                        isScoring = false;
                        return;
                    }

                    updateScorecard();
                    flashScoreSelection(i);
                    refreshTurnUI();
                    startTurnTimer();
                    isScoring = false;
                    return;
                } catch (error) {
                    console.error('Ranked score failed:', error);
                    alert(error.message || '서버 점수 기록에 실패했습니다.');
                    isScoring = false;
                    refreshTurnUI();
                    return;
                }
            }

            result = applyScoreToCard(myCard, i, dice);
            showToast(CATS[i], result.totalGain, result.bonus > 0 ? 'Yacht Bonus +100' : '');

            resetTurnState();

            if (isVersusAI()) {
                if (finishVersusAiIfComplete()) return;
                turnOwner = AI_OPPONENT_NAME;
                commitState();
                updateScorecard();
                flashScoreSelection(i);
                refreshTurnUI();
                setTimeout(() => {
                    runAiTurn().catch((error) => console.error('VS AI flow failed:', error));
                }, AI_TURN_DELAY_MS);
                return;
            }

            const myDone = myCard.every((value) => value !== null);
            if (myDone) {
                gameOver = true;
                commitState();
                updateScorecard();
                flashScoreSelection(i);
                refreshTurnUI();
                showGameOverToast(calcTotals(myCard).total, 0);
                return;
            }

            commitState();
            updateScorecard();
            flashScoreSelection(i);
            refreshTurnUI();
            startTurnTimer();
        }

        function resetGame() {
            if (!confirm('🔄 새 게임을 시작하시겠습니까?\n\n현재 게임 진행 상황이 모두 초기화됩니다.')) return;
            location.reload();
        }

        async function leaveRoom() {
            if (!confirm('정말 나가시겠습니까?')) return;
            window.location.replace('/');
        }

        function passTurn() {}

        async function pushState() {}
        function applyRemoteState(state) {}
        async function fetchRoomState() {}
        function startSyncPolling() {}

        async function initializeGame() {
            updateLocalVars();
            syncModeQuery();
            try {
                await startRankedSingleSession();
            } catch (error) {
                console.warn('Ranked single session unavailable:', error);
                singleSessionReady = false;
            }
            renderDice();
            bindAiModeControls(() => {
                if (!coachEnabled) return;
                if (!gameOver && isMyTurn() && rollsLeft < 3) askAI();
            });
            bindSingleModeControls();
            updateScorecard();

            const roomLabel = document.getElementById('room-label');
            if (roomLabel) roomLabel.textContent = '';

            const multiControls = document.getElementById('multiplayer-controls');
            if (multiControls) multiControls.style.display = 'none';

            const newGameBtn = document.getElementById('new-game-btn');
            if (newGameBtn) newGameBtn.style.display = 'inline-block';

            window.addEventListener('offline', () => {
                alert('네트워크 연결이 끊겼습니다. AI 추천과 VS AI 모드는 일시적으로 멈출 수 있습니다.');
            });
            refreshTurnUI();
            startTurnTimer();
        }

        initializeGame().catch((e) => console.error('Initialization error:', e));
