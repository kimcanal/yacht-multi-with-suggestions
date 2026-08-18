        // --- [전역 변수 설정] ---
        // 멀티플레이 전용이므로 관련 변수를 간소화합니다.
        const params = new URLSearchParams(window.location.search);
        let roomCode = params.get('room') || localStorage.getItem('yacht_room') || '';
        const roomTokenKey = (code) => `yacht_player_token_${code}`;

        // 방 정보가 없으면 즉시 퇴장
        if (!roomCode) {
            alert('잘못된 접근입니다. 로비에서 방을 생성하거나 참가해주세요.');
            window.location.href = '/';
        } else {
            localStorage.setItem('yacht_room', roomCode);
        }

        let username = localStorage.getItem('yacht_username') || '';
        var isObserver = false;
        // 관전 모드 진입: ?mode=observer 파라미터가 있으면 관전자
        if (params.get('mode') === 'observer') {
            isObserver = true;
            username = username || 'obs_' + Math.floor(Math.random()*10000);
            localStorage.setItem('yacht_username', username);
        }
        if (!username) {
            alert('닉네임 정보가 없습니다. 로비에서 다시 입장해주세요.');
            window.location.href = '/';
        }
        let playerToken = isObserver ? '' : localStorage.getItem(roomTokenKey(roomCode));
        if (!isObserver && !playerToken) {
            alert('플레이어 인증 정보가 없습니다. 로비에서 다시 입장해주세요.');
            window.location.href = '/';
        }
        // --- [관전자 입장 처리] ---
        async function tryObserveRoom() {
            if (!roomCode || !isObserver) return;
            try {
                const res = await fetch(`/api/rooms/${roomCode}/observe`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username })
                });
                if (!res.ok) {
                    alert('관전 입장에 실패했습니다.');
                    window.location.href = '/';
                    return;
                }
                const data = await res.json();
                observerCount = Number(data.observers?.length || 0);
                if (Array.isArray(data.players)) roomPlayers = data.players;
                renderObserverSummary();
            } catch (e) {
                alert('관전 입장 중 오류 발생.');
                window.location.href = '/';
            }
        }
        // --- [관전자 UI 처리] ---
        function updateObserverUI() {
            const diceActionRow = document.getElementById('dice-action-row');
            if (isObserver) {
                document.getElementById('player-controls').style.display = 'none';
                document.getElementById('observer-controls').style.display = 'flex';
                if (diceActionRow) diceActionRow.style.display = 'none';
                const banner = document.getElementById('observer-banner');
                if (banner) banner.style.display = 'block';
                document.querySelectorAll('.ai-mode-guide, .ai-mode-row').forEach((element) => {
                    element.style.display = 'none';
                });
                renderObserverSummary();
            } else {
                document.getElementById('player-controls').style.display = 'flex';
                document.getElementById('observer-controls').style.display = 'none';
                if (diceActionRow) diceActionRow.style.display = 'flex';
                const banner = document.getElementById('observer-banner');
                if (banner) banner.style.display = 'none';
                document.querySelectorAll('.ai-mode-guide, .ai-mode-row').forEach((element) => {
                    element.style.display = element.classList.contains('ai-mode-row') ? 'flex' : 'grid';
                });
            }
        }
        let roomVersion = 0;
        let syncTimer = null;
        let isApplyingRemote = false;
        let roomPlayers = [];
        let prevPlayerCount = 0;
        let opponentName = '';
        let turnOwner = null;
        let isRolling = false;
        let scoreRequestInFlight = false;
        let gameOverToastShown = false;
        let connectionLostHandled = false;
        let syncFailures = 0;
        let allowImmediateExit = false;
        let observerCount = 0;
        let roomPhase = 'waiting';
        let endWinner = null;
        let endLoser = null;
        let endReason = null;
        let rematchPendingPlayers = [];
        let rematchWaitingFor = [];
        let rematchRequestInFlight = false;
        const ROOM_SYNC_INTERVAL_VISIBLE_MS = 1200;
        const ROOM_SYNC_INTERVAL_HIDDEN_MS = 4000;
        const ROOM_SYNC_BACKOFF_MAX = 4;
        const ROOM_HEARTBEAT_INTERVAL_MS = 8000;
        const ROOM_REQUEST_TIMEOUT_VISIBLE_MS = 6000;
        const ROOM_REQUEST_TIMEOUT_HIDDEN_MS = 12000;
        const ROOM_CONTACT_GRACE_MS = isObserver ? 90000 : 45000;
        let roomHeartbeatTimer = null;
        let roomEventSource = null;
        let syncRequestInFlight = false;
        let heartbeatRequestInFlight = false;
        let lastRoomContactAt = Date.now();
        let syncPollGeneration = 0;
        const mobileInsightQuery = window.matchMedia('(max-width: 768px)');

        function syncMobileInsightPlacement() {
            const panel = document.getElementById('mobile-insight-panel');
            const diceArea = document.querySelector('.dice-area');
            const mobileSlot = document.getElementById('mobile-insight-slot');
            if (!panel || !diceArea || !mobileSlot) return;
            const destination = mobileInsightQuery.matches ? mobileSlot : diceArea;
            if (panel.parentElement !== destination) destination.appendChild(panel);
        }

        // 편의성 변수 (읽기 전용)
        let dice, kept, rollsLeft, myCard, oppCard, gameOver, aiRec;
        function updateLocalVars() {
            const state = GameState.getState();
            dice = state.dice;
            kept = state.kept;
            rollsLeft = state.rollsLeft;
            myCard = state.myCard;
            oppCard = state.oppCard;
            gameOver = state.gameOver;
            aiRec = state.aiRec;
        }
        updateLocalVars();
        updateObserverUI();

        function isPageHidden() {
            return document.visibilityState === 'hidden';
        }

        function currentRoomRequestTimeoutMs() {
            return isPageHidden() ? ROOM_REQUEST_TIMEOUT_HIDDEN_MS : ROOM_REQUEST_TIMEOUT_VISIBLE_MS;
        }

        function currentSyncIntervalMs() {
            const baseInterval = isPageHidden() ? ROOM_SYNC_INTERVAL_HIDDEN_MS : ROOM_SYNC_INTERVAL_VISIBLE_MS;
            const backoff = Math.min(ROOM_SYNC_BACKOFF_MAX, Math.max(1, 2 ** syncFailures));
            return baseInterval * backoff;
        }

        function markRoomContact() {
            lastRoomContactAt = Date.now();
            syncFailures = 0;
        }

        function hasRoomTimedOutLocally() {
            return (Date.now() - lastRoomContactAt) > ROOM_CONTACT_GRACE_MS;
        }

        function shouldSkipHeartbeat() {
            if (roomEventSource) return false;
            return (Date.now() - lastRoomContactAt) < Math.min(ROOM_HEARTBEAT_INTERVAL_MS * 0.75, currentSyncIntervalMs() * 2.5);
        }

        async function fetchWithTimeout(url, options = {}, timeoutMs = currentRoomRequestTimeoutMs()) {
            if (typeof AbortController !== 'function') {
                return fetch(url, options);
            }
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), timeoutMs);
            try {
                return await fetch(url, {...options, signal: controller.signal});
            } finally {
                clearTimeout(timer);
            }
        }

        function hasRecordedScore(card) {
            return Array.isArray(card) && card.some((value) => value !== null && value !== undefined);
        }

        function getScoreSummaryText(myTotal, oppTotal) {
            if (isObserver) {
                const leftName = roomPlayers[0] || 'Player 1';
                const rightName = roomPlayers[1] || opponentName || endLoser || 'Player 2';
                return `${leftName} ${myTotal} : ${rightName} ${oppTotal}`;
            }
            return `나 ${myTotal} : 상대 ${oppTotal}`;
        }

        function getGameOverPresentation(myTotal, oppTotal) {
            const scoreLine = getScoreSummaryText(myTotal, oppTotal);
            let title = '🎉 게임 종료';
            let detail = scoreLine;
            let status = `🏁 최종 점수 ${scoreLine}`;

            if (endReason === 'timeout' && endWinner && endLoser) {
                if (isObserver) {
                    title = '⏰ 시간 초과 종료';
                    detail = `${endLoser}님 연결 종료, ${endWinner}님 승리`;
                    status = `⏰ ${endLoser}님 연결 종료로 ${endWinner}님 승리`;
                } else if (username === endWinner) {
                    title = '🏆 승리!';
                    detail = `${endLoser}님이 응답하지 않아 승리 처리되었습니다`;
                    status = `🏆 ${endLoser}님 연결 종료로 승리했습니다`;
                } else if (username === endLoser) {
                    title = '😥 패배';
                    detail = '연결이 오래 끊겨 패배 처리되었습니다';
                    status = '😥 연결 종료로 패배 처리되었습니다';
                } else {
                    title = '⏰ 시간 초과 종료';
                    detail = `${endLoser}님 연결 종료, ${endWinner}님 승리`;
                    status = `⏰ ${endLoser}님 연결 종료로 게임이 종료되었습니다`;
                }
                return {title, detail, status};
            }

            if (endReason === 'leave' && endWinner && endLoser) {
                if (isObserver) {
                    title = '🚪 퇴장 종료';
                    detail = `${endLoser}님 퇴장, ${endWinner}님 승리`;
                    status = `🚪 ${endLoser}님 퇴장으로 ${endWinner}님 승리`;
                } else if (username === endWinner) {
                    title = '🏆 승리!';
                    detail = `${endLoser}님이 방을 나가 승리 처리되었습니다`;
                    status = `🏆 ${endLoser}님 퇴장으로 승리했습니다`;
                } else if (username === endLoser) {
                    title = '😥 패배';
                    detail = '방을 나가 패배 처리되었습니다';
                    status = '😥 퇴장으로 패배 처리되었습니다';
                } else {
                    title = '🚪 퇴장 종료';
                    detail = `${endLoser}님 퇴장, ${endWinner}님 승리`;
                    status = `🚪 ${endLoser}님 퇴장으로 게임이 종료되었습니다`;
                }
                return {title, detail, status};
            }

            if (myTotal > oppTotal) title = isObserver ? '🏆 승자 확정' : '🏆 승리!';
            else if (myTotal < oppTotal) title = isObserver ? '📌 결과 확정' : '😥 패배';
            else title = '🤝 무승부';

            return {title, detail, status};
        }

        function copyObserverLink() {
            const buttons = Array.from(document.querySelectorAll('[data-copy-observer-link]'));
            const restore = () => {
                buttons.forEach((button, index) => {
                    button.textContent = index === 0 ? '🔗 관전 링크 복사' : '🔗 링크 복사';
                });
            };
            const observerUrl = `${window.location.origin}${window.location.pathname}?room=${encodeURIComponent(roomCode)}&mode=observer`;
            if (!navigator.clipboard || !navigator.clipboard.writeText) {
                alert(`관전 링크를 복사해 공유해 주세요:\n${observerUrl}`);
                return;
            }
            navigator.clipboard.writeText(observerUrl)
                .then(() => {
                    buttons.forEach((button) => { button.textContent = '복사 완료'; });
                    setTimeout(restore, 1600);
                })
                .catch(() => {
                    alert(`관전 링크를 복사해 공유해 주세요:\n${observerUrl}`);
                    restore();
                });
        }

        function renderObserverSummary() {
            if (!isObserver) return;
            const root = document.getElementById('observer-summary-grid');
            if (!root) return;
            const playerOne = roomPlayers[0] || '플레이어 대기';
            const playerTwo = roomPlayers[1] || '상대 대기';
            const phase = gameOver ? 'finished' : roomPhase;
            const phaseLabel = phase === 'playing' ? '진행 중' : (phase === 'finished' ? '게임 종료' : '대기 중');
            const turnLabel = gameOver ? '종료됨' : (turnOwner || '대기 중');
            const progress = getRoomTurnProgress();
            const progressLabel = (!progress.started && progress.current === 0) ? `대기 중 (0/${progress.total})` : progress.label;
            root.innerHTML = `
                <div class="observer-meta-card">
                    <div class="observer-meta-label">Room</div>
                    <div class="observer-meta-value">${escapeHtml(roomCode)}</div>
                </div>
                <div class="observer-meta-card">
                    <div class="observer-meta-label">Players</div>
                    <div class="observer-meta-value">${escapeHtml(playerOne)} vs ${escapeHtml(playerTwo)}</div>
                </div>
                <div class="observer-meta-card">
                    <div class="observer-meta-label">Current Turn</div>
                    <div class="observer-meta-value">${escapeHtml(turnLabel)}</div>
                </div>
                <div class="observer-meta-card">
                    <div class="observer-meta-label">Turn Progress</div>
                    <div class="observer-meta-value">${escapeHtml(progressLabel)}</div>
                </div>
                <div class="observer-meta-card">
                    <div class="observer-meta-label">Audience</div>
                    <div class="observer-meta-value">관전자 ${observerCount}명 · ${phaseLabel}</div>
                </div>
            `;
        }

        function hasRoomMatchStarted() {
            const filledTurns = countFilledCategories(myCard) + countFilledCategories(oppCard);
            return gameOver || roomPhase === 'playing' || roomPlayers.length >= 2 || filledTurns > 0;
        }

        function getRoomTurnProgress() {
            return getMultiTurnProgress(myCard, oppCard, {
                started: hasRoomMatchStarted(),
                gameOver,
            });
        }

        function updateTurnProgressUI() {
            const progressEl = document.getElementById('turn-progress');
            if (!progressEl) return;
            const progress = getRoomTurnProgress();
            if (!progress.started && progress.current === 0) {
                progressEl.innerText = `턴 진행: 대기 중 (0/${progress.total})`;
                return;
            }
            progressEl.innerText = `턴 진행: ${progress.label}`;
        }

        function shouldWarnBeforeLeave() {
            if (allowImmediateExit || isObserver || gameOver) return false;
            if (roomPlayers.length < 2) return false;
            return rollsLeft < 3 || hasRecordedScore(GameState.getMyCard()) || hasRecordedScore(GameState.getOppCard());
        }

        // --- [타이머 로직] (양쪽 플레이어 시간 표시) ---
        function timeOut(){
            const toast = document.getElementById('score-toast');
            toast.innerHTML = `<div class="toast-cat">⏰ 시간 초과!</div><div class="toast-score">자동으로 진행합니다...</div>`;
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
            } catch (e) { console.warn('Toast audio failed:', e); }
            setTimeout(() => toast.classList.remove('show'), 1500);
        }

        let timerInterval = null;
        let turnLeftSeconds = null;

        function updateTurnTimer() {
            if (turnLeftSeconds == null || gameOver || rollsLeft === 0) {
                document.getElementById('timer-bar').style.display = 'none';
                return;
            }
            const timerBar = document.getElementById('timer-bar');
            timerBar.style.display = 'block';

            if (isObserver) {
                // [수정됨] 관전자는 고정된 상대 이름이 아니라, 실시간 'turnOwner'를 표시
                const currentTurnName = turnOwner || '플레이어';
                timerBar.innerHTML = `⏳ ${currentTurnName} 턴: <span id="timer-count">${turnLeftSeconds}</span>초`;
                timerBar.style.color = '#ffd700';
            } else if (isMyTurn()) {
                // [플레이어 - 내 턴]
                timerBar.innerHTML = `⏳ <span id="timer-count">${turnLeftSeconds}</span>초 남았습니다`;
                timerBar.style.color = '#ff6b6b';
            } else {
                // [플레이어 - 상대 턴]
                const oppName = opponentName || '상대방';
                timerBar.innerHTML = `⏳ ${oppName} 턴: <span id="timer-count">${turnLeftSeconds}</span>초`;
                timerBar.style.color = '#ffd700';
            }
        }

        function startTurnTimer() {
            if (timerInterval) return;

            // 시간 정보가 있고 게임 중이면 무조건 표시
            if (turnLeftSeconds != null && !gameOver && rollsLeft > 0) {
                updateTurnTimer();
                timerInterval = setInterval(() => {
                    if (turnLeftSeconds > 0) {
                        turnLeftSeconds--;
                    }
                    updateTurnTimer();

                    if (turnLeftSeconds <= 0 && isMyTurn() && !gameOver && !isRolling) {
                        clearTurnTimer();
                        timeOut();
                        // Timeout advancement is server-authoritative.  This
                        // avoids a paused/modified browser deciding the dice
                        // or score transition for a multiplayer room.
                        fetchRoomState();
                    }
                }, 1000);
            } else {
                document.getElementById('timer-bar').style.display = 'none';
            }
        }

        function clearTurnTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            document.getElementById('timer-bar').style.display = 'none';
        }

        function showStatusToast(title, detail = '', timeoutMs = 1800) {
            const toast = document.getElementById('score-toast');
            const detailHtml = detail ? `<div class="toast-score" style="font-size:0.9em;">${escapeHtml(detail)}</div>` : '';
            toast.innerHTML = `<div class="toast-cat">${escapeHtml(title)}</div>${detailHtml}`;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), timeoutMs);
        }

        function stopSyncPolling() {
            syncPollGeneration += 1;
            if (syncTimer) {
                clearTimeout(syncTimer);
                syncTimer = null;
            }
        }

        function scheduleNextSyncPoll(delayMs = currentSyncIntervalMs(), generation = syncPollGeneration) {
            if (!roomCode || connectionLostHandled || generation !== syncPollGeneration) return;
            syncTimer = setTimeout(async () => {
                if (generation !== syncPollGeneration) return;
                syncTimer = null;
                await fetchRoomState();
                scheduleNextSyncPoll(currentSyncIntervalMs(), generation);
            }, delayMs);
        }

        function startSyncPolling(options = {}) {
            const {immediate = false} = options;
            stopSyncPolling();
            const generation = syncPollGeneration;
            if (immediate) {
                fetchRoomState().finally(() => scheduleNextSyncPoll(currentSyncIntervalMs(), generation));
                return;
            }
            scheduleNextSyncPoll(currentSyncIntervalMs(), generation);
        }

        function stopRoomEvents() {
            if (roomEventSource) {
                roomEventSource.close();
                roomEventSource = null;
            }
        }

        function startRoomEvents(options = {}) {
            const {immediate = false} = options;
            stopRoomEvents();
            if (typeof EventSource !== 'function' || document.visibilityState === 'hidden') {
                startSyncPolling({immediate});
                return;
            }

            stopSyncPolling();
            if (immediate) fetchRoomState();
            const qs = new URLSearchParams({sv: String(roomVersion), interval_ms: '800'});
            if (lastReactionId) qs.set('reaction_id', lastReactionId);
            const source = new EventSource(`/api/rooms/${roomCode}/events?${qs.toString()}`);
            roomEventSource = source;
            source.onopen = () => {
                if (source === roomEventSource) stopSyncPolling();
            };
            source.addEventListener('room_state', (event) => {
                if (source !== roomEventSource || connectionLostHandled) return;
                try {
                    const notice = JSON.parse(event.data || '{}');
                    const remoteVersion = Number(notice.version || 0);
                    if (remoteVersion !== roomVersion || notice.room_phase !== roomPhase) {
                        fetchRoomState();
                    }
                } catch (error) {
                    console.warn('room event parse failed', error);
                }
            });
            source.addEventListener('reaction', (event) => {
                if (source !== roomEventSource || connectionLostHandled) return;
                try {
                    showReaction(JSON.parse(event.data || '{}'));
                } catch (error) {
                    console.warn('reaction event parse failed', error);
                }
            });
            source.addEventListener('room_closed', () => {
                if (source === roomEventSource) handleConnectionLost('방이 종료되어 로비로 이동합니다.');
            });
            source.onerror = () => {
                if (source !== roomEventSource || connectionLostHandled) return;
                // EventSource의 기본 재연결은 유지하고, 연결 중에만 polling을 fallback으로 쓴다.
                startSyncPolling({immediate: true});
            };
        }

        function stopRoomHeartbeat() {
            if (roomHeartbeatTimer) {
                clearInterval(roomHeartbeatTimer);
                roomHeartbeatTimer = null;
            }
        }

        function startRoomHeartbeat(options = {}) {
            const {immediate = false} = options;
            if (roomHeartbeatTimer) return;
            if (immediate) {
                sendRoomHeartbeat({immediate: true});
            }
            roomHeartbeatTimer = setInterval(() => {
                sendRoomHeartbeat();
            }, ROOM_HEARTBEAT_INTERVAL_MS);
        }

        function handleConnectionLost(msg = '상대방과의 연결이 끊어졌습니다. 로비로 이동합니다.') {
            if (connectionLostHandled) return;
            connectionLostHandled = true;
            allowImmediateExit = true;
            clearTurnTimer();
            stopRoomEvents();
            stopSyncPolling();
            stopRoomHeartbeat();
            localStorage.removeItem('yacht_room');
            showStatusToast('연결 종료', msg, 1500);
            setTimeout(() => window.location.replace('/'), 1500);
        }

        window.addEventListener('offline', () => {
            showStatusToast('네트워크 불안정', '재연결을 시도하고 있습니다.', 1400);
        });

        window.addEventListener('online', () => {
            if (connectionLostHandled) return;
            startRoomEvents({immediate: true});
            sendRoomHeartbeat({immediate: true});
            showStatusToast('연결 복구', '방 상태를 다시 확인하고 있습니다.', 1400);
        });

        document.addEventListener('visibilitychange', () => {
            if (connectionLostHandled || !roomCode) return;
            if (document.visibilityState === 'visible') {
                startRoomEvents({immediate: true});
                sendRoomHeartbeat({immediate: true});
            } else {
                stopRoomEvents();
                startSyncPolling({immediate: false});
            }
        });

        function showGameOverToast(myTotal, oppTotal) {
            if (gameOverToastShown) return;
            const toast = document.getElementById('score-toast');
            const {title, detail} = getGameOverPresentation(myTotal, oppTotal);

            toast.innerHTML = `<div class="toast-cat">${title}</div><div class="toast-score">${detail}</div>`;
            toast.classList.add('show');
            playTurnToastSound();
            gameOverToastShown = true;
            setTimeout(() => toast.classList.remove('show'), 2800);
        }

        function updateRematchUI() {
            const rematchBtn = document.getElementById('rematch-btn');
            if (!rematchBtn) return;

            const canShow =
                !isObserver &&
                GameState.isGameOver() &&
                roomPlayers.length >= 2 &&
                !connectionLostHandled;

            if (!canShow) {
                rematchBtn.style.display = 'none';
                rematchBtn.disabled = true;
                return;
            }

            const myRequested = rematchPendingPlayers.includes(username);
            const opponentRequested = roomPlayers.some((player) => player !== username && rematchPendingPlayers.includes(player));

            rematchBtn.style.display = 'inline-flex';
            rematchBtn.disabled = rematchRequestInFlight || myRequested;
            rematchBtn.style.opacity = rematchBtn.disabled ? '0.72' : '1';

            if (opponentRequested && !myRequested) {
                rematchBtn.textContent = '⚡ 재대결 수락';
            } else if (myRequested) {
                rematchBtn.textContent = '⏳ 재대결 대기 중';
            } else {
                rematchBtn.textContent = '🔁 재대결 신청';
            }
        }

        async function requestRematch() {
            if (isObserver || !GameState.isGameOver() || roomPlayers.length < 2 || rematchRequestInFlight) return;

            rematchRequestInFlight = true;
            updateRematchUI();
            try {
                const r = await fetchWithTimeout(
                    `/api/rooms/${roomCode}/rematch`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username, player_token: playerToken}),
                    },
                    currentRoomRequestTimeoutMs(),
                );
                const data = await r.json();

                if (r.status === 404) {
                    handleConnectionLost('방 연결이 종료되었습니다. 로비로 이동합니다.');
                    return;
                }
                if (r.status === 403 && data.error === '참가자 인증 실패') {
                    handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                    return;
                }
                if (!r.ok) {
                    throw new Error(data.error || `HTTP ${r.status}`);
                }

                markRoomContact();
                rematchPendingPlayers = Array.isArray(data.rematch_pending_players) ? data.rematch_pending_players : [];
                rematchWaitingFor = Array.isArray(data.rematch_waiting_for) ? data.rematch_waiting_for : [];

                if (data.status === 'started') {
                    showStatusToast('재대결 시작', '새 경기를 불러오고 있습니다.', 1200);
                    await fetchRoomState();
                } else {
                    const waitingForOpponent = rematchWaitingFor.find((player) => player !== username) || '상대';
                    showStatusToast('재대결 신청', `${waitingForOpponent} 님 동의를 기다리는 중입니다.`, 1400);
                    refreshTurnUI();
                }
            } catch (e) {
                console.error('rematch failed', e);
                showStatusToast('재대결 실패', e.message || '잠시 후 다시 시도해 주세요.', 1500);
            } finally {
                rematchRequestInFlight = false;
                updateRematchUI();
            }
        }

        const isMyTurn = () => {
            if (!turnOwner) return false;
            return turnOwner === username;
        };

        // --- [서버 동기화] ---
        async function fetchRoomState() {
            if (!roomCode || syncRequestInFlight || connectionLostHandled) return;
            syncRequestInFlight = true;
            const qs = new URLSearchParams();
            qs.set('u', username);
            qs.set('sv', String(roomVersion));
            try {
                const r = await fetchWithTimeout(
                    `/api/rooms/${roomCode}?${qs.toString()}`,
                    {
                        cache: 'no-store',
                        headers: isObserver || !playerToken ? {} : {'X-Player-Token': playerToken},
                    },
                    currentRoomRequestTimeoutMs(),
                );
                if (r.status === 404) {
                    handleConnectionLost('방 정보를 찾을 수 없습니다. 로비로 이동합니다.');
                    return;
                }
                if (r.status === 403) {
                    handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                    return;
                }

                const data = await r.json();
                if (!r.ok) {
                    throw new Error(data.error || `HTTP ${r.status}`);
                }

                markRoomContact();
                syncReactions(data.reactions);
                observerCount = Number(data.observer_count ?? (Array.isArray(data.observers) ? data.observers.length : observerCount));
                roomPhase = data.room_phase || roomPhase;
                rematchPendingPlayers = Array.isArray(data.rematch_pending_players) ? data.rematch_pending_players : [];
                rematchWaitingFor = Array.isArray(data.rematch_waiting_for) ? data.rematch_waiting_for : [];
                if (data.players) {
                    roomPlayers = data.players;
                    if (!isObserver && !roomPlayers.includes(username)) {
                        handleConnectionLost('현재 방 참가자 목록에서 제외되었습니다. 로비로 이동합니다.');
                        return;
                    }
                    const opp = roomPlayers.find(p => p !== username);
                    if (opp && opp !== opponentName) {
                        opponentName = opp;
                    }
                }
                updateObserverUI();
                if (data.state) {
                    turnLeftSeconds = data.state.turn_left_seconds != null ? data.state.turn_left_seconds : null;
                    if (data.unchanged) {
                        if (typeof data.state.version === 'number') {
                            roomVersion = Math.max(roomVersion, data.state.version);
                        }
                        refreshTurnUI();
                        updateTurnTimer();
                        renderObserverSummary();
                    } else {
                        applyRemoteState(data.state);
                    }
                }
            } catch (e) {
                console.warn('pull failed', e);
                syncFailures++;
                if (hasRoomTimedOutLocally()) {
                    handleConnectionLost('연결 상태를 오래 확인할 수 없어 로비로 이동합니다.');
                }
            } finally {
                syncRequestInFlight = false;
            }
        }

        async function sendRoomHeartbeat(options = {}) {
            const {immediate = false} = options;
            if (!roomCode || !username || connectionLostHandled) return;
            if (!immediate && shouldSkipHeartbeat()) return;
            if (heartbeatRequestInFlight && !immediate) return;
            heartbeatRequestInFlight = true;
            try {
                const r = await fetchWithTimeout(
                    `/api/rooms/${roomCode}/heartbeat`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        cache: 'no-store',
                        body: JSON.stringify({
                            username,
                            player_token: isObserver ? undefined : playerToken,
                        }),
                    },
                    immediate ? 4000 : currentRoomRequestTimeoutMs(),
                );
                if (r.status === 404) {
                    handleConnectionLost('방 연결이 종료되었습니다. 로비로 이동합니다.');
                    return;
                }
                if (r.status === 403) {
                    handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                    return;
                }

                const data = await r.json();
                if (!r.ok) {
                    throw new Error(data.error || `HTTP ${r.status}`);
                }

                markRoomContact();
                observerCount = Number(data.observer_count ?? observerCount);
                roomPhase = data.room_phase || roomPhase;
                renderObserverSummary();
            } catch (e) {
                console.warn('heartbeat failed', e);
                if (hasRoomTimedOutLocally()) {
                    handleConnectionLost('방 연결이 오래 끊겨 로비로 이동합니다.');
                }
            } finally {
                heartbeatRequestInFlight = false;
            }
        }

        function refreshTurnUI() {
            const statusEl = document.getElementById('game-status');
            if (!statusEl) return;
            updateTurnProgressUI();

            const passBtn = document.getElementById('pass-turn-btn');
            if (GameState.isGameOver()) {
                const myTotal = calcTotals(GameState.getMyCard()).total;
                const oppTotal = calcTotals(GameState.getOppCard()).total;
                let statusText = getGameOverPresentation(myTotal, oppTotal).status;
                if (!isObserver && roomPlayers.length >= 2) {
                    const myRequested = rematchPendingPlayers.includes(username);
                    const opponentRequested = roomPlayers.some((player) => player !== username && rematchPendingPlayers.includes(player));
                    if (myRequested) {
                        statusText += ' · 재대결 동의 대기 중';
                    } else if (opponentRequested) {
                        statusText += ' · 상대가 재대결을 원합니다';
                    } else {
                        statusText += ' · 한 판 더 할 수 있어요';
                    }
                }
                statusEl.innerText = statusText;
                clearTurnTimer();
                if (passBtn) passBtn.style.display = 'none';
                updateRematchUI();
                updateDice();
                return;
            }

            // 타이머 일시정지 로직을 위한 변수
            let timerPaused = false;

            if (isObserver) {
                // [수정됨] 관전자: 현재 턴 주인의 이름을 표시
                const currentTurnName = turnOwner || '플레이어';
                statusEl.innerText = `🎲 ${currentTurnName} 님의 턴입니다`;
                // 관전자는 선공권 넘기기 버튼 숨김
                if(passBtn) passBtn.style.display = 'none';
            } else {
                // [플레이어] 기존 로직 유지
                if (!opponentName || roomPlayers.length < 2) {
                    statusEl.innerText = '⏳ 상대방 입장 대기 중...';
                } else if (!isMyTurn()) {
                    statusEl.innerText = '⏸️ 상대 턴입니다';
                } else {
                    statusEl.innerText = '🎲 주사위를 돌려주세요';
                }

                // 선공권 넘기기 버튼 로직
                if (passBtn) {
                    const myEmpty = GameState.getMyCard().every(v => v === null);
                    const oppEmpty = GameState.getOppCard().every(v => v === null);
                    if (myEmpty && oppEmpty && rollsLeft === 3 && !gameOver && opponentName && roomPlayers.length >= 2) {
                        timerPaused = true;
                    }
                    const canPass = isMyTurn() && timerPaused;
                    passBtn.style.display = canPass ? 'inline-flex' : 'none';
                }
            }

            updateRematchUI();
            updateDice();
            // timerPaused 변수 적용
            if (turnLeftSeconds != null && !gameOver && !timerPaused) {
                startTurnTimer();
            } else {
                clearTurnTimer();
            }
        }

        function updateDice() {
            for (let i = 0; i < 5; i++) {
                const d = document.getElementById(`die-${i}`);
                const c = document.getElementById(`die-container-${i}`);
                if (!d) continue;

                c.classList.toggle('dice-unrolled', rollsLeft === 3 && !isRolling && !gameOver);
                if (isRolling && !kept[i]) {
                    d.classList.add('rolling');
                } else {
                    d.classList.remove('rolling');
                }

                if (GameState.getKept()[i]) {
                    c.classList.add('locked');
                    d.querySelectorAll('.die-face').forEach(f => f.style.borderColor = '#00ffcc');
                } else {
                    c.classList.remove('locked');
                    d.querySelectorAll('.die-face').forEach(f => f.style.borderColor = 'rgba(200,200,200,0.5)');
                }

                const val = GameState.getDice()[i] || 1;
                d.dataset.value = String(val);

                const keepBtn = document.getElementById(`keep-${i}`);
                const keepText = document.getElementById(`keep-text-${i}`);
                if (keepBtn && keepText) {
                    keepBtn.className = 'keep-btn';

                    if (rollsLeft >= 3 || rollsLeft === 0 || gameOver || isRolling || !isMyTurn()) {
                        keepBtn.disabled = true;
                        keepBtn.style.opacity = '0.5';
                        keepBtn.style.cursor = 'not-allowed';
                    } else {
                        keepBtn.disabled = false;
                        keepBtn.style.opacity = '1';
                        keepBtn.style.cursor = 'pointer';
                    }

                    if (kept[i]) {
                        keepBtn.classList.add('active-keep');
                        keepBtn.style.borderColor = '#00ff00';
                    } else {
                        keepBtn.style.borderColor = 'rgba(255, 255, 255, 0.3)';
                    }

                    keepBtn.style.boxShadow = 'none';

                    keepText.innerHTML = kept[i] ? '✓ KEEP' : 'KEEP';
                }
                const lbl = document.getElementById(`lock-${i}`);
                if (lbl) lbl.innerText = '';
            }
            const boardAiRec = GameState.getAiRec ? GameState.getAiRec() : aiRec;
            applyAiDiceHints(boardAiRec, { enabled: !isObserver && isMyTurn() && !gameOver });
            document.getElementById('rolls-left').innerText = GameState.getRollsLeft();
            const waitingForOpponent = !opponentName || roomPlayers.length < 2;
            document.getElementById('roll-btn').disabled = GameState.getRollsLeft() <= 0 || GameState.isGameOver() || isRolling || !isMyTurn() || waitingForOpponent;
            updateQuickScoreTargets(GameState.getMyCard(), {
                active: !isObserver && !isRolling && !gameOver && rollsLeft < 3 && isMyTurn(),
                dice: GameState.getDice(),
            });
            const scoreJump = document.getElementById('mobile-score-jump');
            if (scoreJump) {
                scoreJump.hidden = isObserver || isRolling || gameOver || rollsLeft >= 3 || !isMyTurn();
            }
        }

        function jumpToScorecard() {
            const scorecardArea = document.querySelector('.scorecard-area');
            if (!scorecardArea) return;
            scorecardArea.scrollIntoView({behavior: 'smooth', block: 'start'});
            window.setTimeout(() => {
                scorecardArea.querySelector('.score-ready')?.focus({preventScroll: true});
            }, 350);
        }

        function toggleLock(i) {
            if (isObserver || rollsLeft >= 3 || rollsLeft <= 0 || gameOver || isRolling || !isMyTurn()) return;
            kept[i] = kept[i] ? 0 : 1;
            GameState.setKept(kept);
            updateDice();
            pushState();
            playKeepSound();
        }

        function refreshInsightPanels() {
            const aiPerspective = isObserver ? `${turnOwner || '플레이어'} 턴 기준` : (isMyTurn() ? '내 턴 기준' : '상대 턴 기준');
            renderAiPanel('ai-breakdown', GameState.getAiRec(), { perspective: aiPerspective });

            const leftLabel = isObserver ? (roomPlayers[0] || 'Player 1') : '나';
            const rightLabel = isObserver ? (roomPlayers[1] || 'Player 2') : (opponentName || '상대');
            const payload = {
                my_scorecard: GameState.getMyCard(),
                opp_scorecard: GameState.getOppCard(),
            };
            const myTurnActive = turnOwner === username || (isObserver && turnOwner === roomPlayers[0]);
            const oppTurnActive = (!isObserver && turnOwner === opponentName) || (isObserver && turnOwner === roomPlayers[1]);
            if (myTurnActive && GameState.getRollsLeft() < 3) {
                payload.my_dice = dice;
                payload.my_rolls_left = GameState.getRollsLeft();
            } else if (oppTurnActive && GameState.getRollsLeft() < 3) {
                payload.opp_dice = dice;
                payload.opp_rolls_left = GameState.getRollsLeft();
            }
            WinProbabilityPanel.request('win-prob-panel', payload, {
                readyToCompare: roomPlayers.length >= 2,
                leftLabel,
                rightLabel,
            });
        }

        function buildStatePayload() {
            return {
                username,
                kept: [...kept],
                turn: turnOwner || username,
                game_over: gameOver,
                player_token: playerToken,
                winner: endWinner,
                loser: endLoser,
                end_reason: endReason,
            };
        }

        async function pushState({ critical = false, attempts = 3 } = {}) {
            if (!roomCode || !username || isApplyingRemote) return false;
            const payload = JSON.stringify(buildStatePayload());
            for (let attempt = 1; attempt <= attempts; attempt++) {
                try {
                    const r = await fetchWithTimeout(
                        `/api/rooms/${roomCode}/sync`,
                        {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: payload,
                        },
                        currentRoomRequestTimeoutMs(),
                    );
                    const data = await r.json();
                    if (r.status === 404) {
                        handleConnectionLost('방 연결이 종료되었습니다. 로비로 이동합니다.');
                        return false;
                    }
                    if (r.status === 403 && data.error === '참가자 인증 실패') {
                        handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                        return false;
                    }
                    if (!r.ok) {
                        throw new Error(data.error || `HTTP ${r.status}`);
                    }
                    markRoomContact();
                    if (data.state && typeof data.state.version === 'number') {
                        roomVersion = data.state.version;
                    }
                    return true;
                } catch (e) {
                    console.warn(`sync failed (attempt ${attempt}/${attempts})`, e);
                    if (attempt < attempts) {
                        await new Promise((resolve) => setTimeout(resolve, 350 * attempt));
                    }
                }
            }
            // 모든 재시도 실패: 낙관적 로컬 상태가 서버와 어긋났을 수 있으므로
            // 다음 폴링에서 서버 권위 상태를 강제로 다시 받아 재동기화한다.
            if (critical) {
                roomVersion = -1;
                showStatusToast('⚠️ 동기화 실패', '방금 동작이 서버에 반영되지 않았습니다. 자동으로 다시 맞춥니다...', 3200);
                fetchRoomState();
            }
            return false;
        }

function applyRemoteState(state) {
    if (!state) return;
    if (typeof state.version === 'number' && state.version <= roomVersion) return;
    isApplyingRemote = true;
    roomVersion = state.version || roomVersion;
    const wasGameOver = GameState.isGameOver();

    const prevTurnOwner = turnOwner;
    const playerDice = state.player_dice || {};
    const playerKept = state.player_kept || {};
    const playerRollsLeft = state.player_rolls_left || {};

    // 1. 관전자 모드일 때 플레이어 식별 (방장 vs 참가자)
    let p1Name = roomPlayers[0]; // 보통 방장
    let p2Name = roomPlayers[1]; // 참가자
    endWinner = state.winner || null;
    endLoser = state.loser || null;
    endReason = state.end_reason || null;

    // 2. 현재 턴 주인의 주사위 상태 가져오기
    const currentTurnOwner = state.turn;
    const fallbackDice = [1,1,1,1,1];
    const fallbackKept = [0,0,0,0,0];

    let diceToShow = [1,1,1,1,1];
    let keptToShow = [0,0,0,0,0];
    let rollsToShow = 3;

    if (currentTurnOwner && playerDice[currentTurnOwner]) {
        diceToShow = playerDice[currentTurnOwner] || fallbackDice;
        keptToShow = playerKept[currentTurnOwner] || fallbackKept;
        rollsToShow = playerRollsLeft[currentTurnOwner] ?? 3;
    }

    GameState.setDice(diceToShow);
    GameState.setKept(keptToShow);
    GameState.setRollsLeft(rollsToShow);
    GameState.setGameOver(state.game_over ?? GameState.isGameOver());
    if (state.game_over) roomPhase = 'finished';
    else if (roomPlayers.length >= 2) roomPhase = 'playing';

    // 3. 플레이어 목록 업데이트
    const newPlayers = state.players || [];
    roomPlayers = newPlayers;

    // 상대방 이름 업데이트 (플레이어 입장에서)
    if (!isObserver && !opponentName && roomPlayers.length > 1) {
        const opp = roomPlayers.find(p => p !== username);
        if (opp) opponentName = opp;
    }

    if (state.turn) turnOwner = state.turn;

    const scores = state.scores || {};
    const scorePlayers = Object.keys(scores);

    // 4. 점수판 데이터 매핑 (가장 중요한 부분!)

    if (isObserver) {
        // [관전자 로직] 나/상대 개념 없이 P1(왼쪽), P2(오른쪽) 고정
        p1Name = roomPlayers[0] || scorePlayers[0] || endWinner || 'Player 1';
        p2Name = roomPlayers[1] || scorePlayers.find(name => name !== p1Name) || endLoser || 'Player 2';

        if (scores[p1Name]) GameState.setMyCard(scores[p1Name]);
        else GameState.setMyCard(Array(12).fill(null));

        if (scores[p2Name]) GameState.setOppCard(scores[p2Name]);
        else GameState.setOppCard(Array(12).fill(null));

    } else {
        // [플레이어 로직] 기존 유지 (내 점수 vs 상대 점수)
        if (scores[username]) GameState.setMyCard(scores[username]);

        const guessedOpp = Object.keys(scores).find(n => n !== username) || opponentName;
        if (guessedOpp && scores[guessedOpp]) {
            opponentName = guessedOpp;
            GameState.setOppCard(scores[guessedOpp]);
        }
    }

    // 5. AI 추천은 현재 브라우저가 자신의 주사위로 계산한 결과만 사용한다.
    // 이전 버전의 방 상태에 남아 있는 상대 추천도 다음 턴에 표시하지 않는다.
    if (prevTurnOwner !== currentTurnOwner) {
        GameState.setAiRec(null);
    }
    updateLocalVars();

    // 내 턴 알림 (플레이어만)
    if (!isObserver && prevTurnOwner && prevTurnOwner !== username && turnOwner === username) {
        const toast = document.getElementById('score-toast');
        toast.innerHTML = `<div style="font-size:1.1em; font-weight:bold; color:#00ff00;">✨ 당신의 턴입니다!</div>`;
        toast.classList.add('show');
        playTurnToastSound();
        setTimeout(() => toast.classList.remove('show'), 1500);
    }

    refreshInsightPanels();
    renderObserverSummary();

    if (wasGameOver && !GameState.isGameOver()) {
        gameOverToastShown = false;
        matchWinHistory = [];
        rematchPendingPlayers = [];
        rematchWaitingFor = [];
        const starterName = turnOwner || '새 선공';
        showStatusToast('재대결 시작', `${starterName} 님 선공으로 다시 시작합니다.`, 1700);
    }

    // 게임 종료 처리
    if (GameState.isGameOver()) {
        const myTotal = calcTotals(GameState.getMyCard()).total;
        const oppTotal = calcTotals(GameState.getOppCard()).total;
        showGameOverToast(myTotal, oppTotal);
    }

    refreshTurnUI();
    updateDice();
    updateScorecard(); // 여기서 이름표 업데이트
    isApplyingRemote = false;
}

        async function rollDice() {
            if (rollsLeft <= 0 || gameOver || isRolling || !isMyTurn()) return;
            if (!opponentName || roomPlayers.length < 2) {
                alert('상대방이 입장할 때까지 기다려주세요!');
                return;
            }
            clearTurnTimer();
            const keptForRoll = [...kept];

            playDiceRollSound();

            isRolling = true;
            aiRec = null;
            GameState.setAiRec(null);
            renderAiStatus('ai-breakdown', '🎲 계산 중...');
            updateDice();
            updateScorecard();

            startDiceRollAnimation(keptForRoll);

            setTimeout(async () => {
                try {
                    // 멀티플레이: 항상 서버에서 주사위 굴림
                    const r = await fetchWithTimeout(
                        `/api/rooms/${roomCode}/roll`,
                        {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                username,
                                kept: keptForRoll,
                                player_token: playerToken,
                                expected_version: roomVersion,
                            }),
                        },
                        currentRoomRequestTimeoutMs(),
                    );
                    const data = await r.json();
                    if (r.status === 404) {
                        handleConnectionLost('방 연결이 종료되었습니다. 로비로 이동합니다.');
                        stopDiceRollAnimation();
                        isRolling = false;
                        return;
                    }
                    if (r.status === 403 && data.error === '참가자 인증 실패') {
                        handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                        stopDiceRollAnimation();
                        isRolling = false;
                        return;
                    }
                    if (r.status === 409) {
                        fetchRoomState();
                        throw new Error(data.error || '방 상태가 변경되었습니다. 다시 동기화합니다.');
                    }
                    if (!r.ok) {
                        throw new Error(data.error || `HTTP ${r.status}`);
                    }
                    if (data.dice && typeof data.rolls_left === 'number') {
                        markRoomContact();
                        if (data.state && typeof data.state.version === 'number') {
                            roomVersion = data.state.version;
                        }
                        dice = data.dice;
                        rollsLeft = data.rolls_left;
                        GameState.setDice(dice);
                        kept = [...keptForRoll];
                        GameState.setKept(kept);
                        GameState.setRollsLeft(rollsLeft);
                        turnLeftSeconds = 30;
                    } else {
                        alert('주사위 굴림 실패');
                        stopDiceRollAnimation();
                        isRolling = false;
                        return;
                    }

                    stopDiceRollAnimation();
                    isRolling = false;
                    updateDice();
                    updateScorecard();
                    refreshTurnUI();

                    if (calcScore(dice, 11) === 50) {
                        const toast = document.getElementById('score-toast');
                        if (myCard[11] >= 50) {
                            toast.innerHTML = `<div class="toast-cat">🏆 YACHT BONUS 가능!</div><div class="toast-score" style="font-size:0.9em;">다른 칸에 점수 기록 시 +100점</div>`;
                        } else if (myCard[11] === 0) {
                            toast.innerHTML = `<div class="toast-cat" style="color:#ff6b6b;">😢 YACHT 성공이지만</div><div class="toast-score" style="color:#ff6b6b; font-size:0.85em;">Bonus 불가능 (0점 처리됨)</div>`;
                        } else {
                            toast.innerHTML = `<div class="toast-cat">🎲 YACHT 성공!</div><div class="toast-score">50점</div>`;
                        }
                        toast.classList.add('show');
                        playTurnToastSound();
                        setTimeout(() => toast.classList.remove('show'), 2000);
                    }

                    await askAI();
                    pushState();
                } catch (e) {
                    console.error('Roll failed:', e);
                    stopDiceRollAnimation();
                    isRolling = false;
                }
            }, 720);
        }

        async function askAI() {
            if (gameOver || !isMyTurn()) return;
            try {
                const open_categories = myCard.map((v, i) => v === null ? i : null).filter(v => v !== null);
                const r = await fetch('/api/recommend', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({dice, rolls_left: rollsLeft, scorecard: myCard, open_categories, strategy_mode: getAiMode()})
                });
                const payload = await r.json();
                if (!r.ok || payload.error) {
                    throw new Error(payload.message || payload.error || 'AI 추천 요청 실패');
                }
                aiRec = payload;
                GameState.setAiRec(aiRec);
                refreshInsightPanels();
                updateScorecard();
                updateDice();
            } catch (e) {
                console.error(e);
                renderAiStatus('ai-breakdown', `추천 실패: ${e.message || '잠시 후 다시 시도해 주세요.'}`, 'error');
            }
        }

function updateScorecard() {
    const el = document.getElementById('scorecard');
    if (!el) return;
    updateScoreHelp();
    updateTurnProgressUI();

    const safeMyCard = Array.isArray(myCard) ? myCard : Array(12).fill(null);
    const safeOppCard = Array.isArray(oppCard) ? oppCard : Array(12).fill(null);

    if (isObserver) {
        const p1 = (roomPlayers && roomPlayers[0]) ? roomPlayers[0] : 'Player 1';
        const p2 = (roomPlayers && roomPlayers[1]) ? roomPlayers[1] : 'Waiting...';
        el.innerHTML = renderCompareBoard(safeMyCard, safeOppCard, {
            leftTitle: p1,
            rightTitle: p2,
            leftShortLabel: 'P1',
            rightShortLabel: 'P2',
            leftActive: turnOwner === p1,
            rightActive: turnOwner === p2,
            leftInteractive: false,
            previewIds: false,
        });
    } else {
        const oppLabel = opponentName || '상대 대기 중';
        el.innerHTML = renderCompareBoard(myCard, oppCard, {
            leftTitle: `나 (${username})`,
            rightTitle: `상대 (${oppLabel})`,
            leftShortLabel: '나',
            rightShortLabel: '상대',
            leftActive: isMyTurn(),
            rightActive: !isMyTurn(),
            leftInteractive: true,
            previewIds: true,
        });
    }

    const review = document.getElementById('game-review');
    if (review) {
        review.innerHTML = gameOver
            ? renderGameReview(safeMyCard, { opponentTotal: calcTotals(safeOppCard).total })
            : '';
    }
    const boardAiRec = GameState.getAiRec ? GameState.getAiRec() : aiRec;
    applyAiScoreHints(boardAiRec, { enabled: !isObserver && isMyTurn() && !gameOver });
}

// 게임 중(게임오버 전)에 페이지를 떠나려 할 때 경고창 띄우기
window.addEventListener('beforeunload', (e) => {
    if (!shouldWarnBeforeLeave()) return;

    // 표준 방식: 사용자에게 확인 메시지 유도
    e.preventDefault();
    e.returnValue = '';
});

        function showToast(category, score) {
            const toast = document.getElementById('score-toast');
            toast.innerHTML = `<div class="toast-cat">${category}</div><div class="toast-score">+${score}</div>`;
            toast.classList.add('show');
            playScoreSelectSound();
            setTimeout(() => toast.classList.remove('show'), 1500);
        }

        function chooseBestOpenCategory(card, currentDice) {
            let bestIdx = null;
            let bestScore = -1;
            for (let i = 0; i < 12; i++) {
                if (card[i] !== null) continue;
                const score = calcScore(currentDice, i);
                if (bestIdx === null || score > bestScore) {
                    bestIdx = i;
                    bestScore = score;
                }
            }
            return bestIdx;
        }

        async function pickCategory(i) {
            if (!isMyTurn() || myCard[i] !== null || rollsLeft === 3 || gameOver || scoreRequestInFlight) return;
            scoreRequestInFlight = true;
            try {
                const r = await fetchWithTimeout(
                    `/api/rooms/${roomCode}/score`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            username,
                            category_idx: i,
                            player_token: playerToken,
                            expected_version: roomVersion,
                        }),
                    },
                    currentRoomRequestTimeoutMs(),
                );
                const data = await r.json();
                if (r.status === 404) {
                    handleConnectionLost('방 연결이 종료되었습니다. 로비로 이동합니다.');
                    return;
                }
                if (r.status === 403 && data.error === '참가자 인증 실패') {
                    handleConnectionLost('참가 인증이 만료되었습니다. 로비에서 다시 입장해 주세요.');
                    return;
                }
                if (r.status === 409) {
                    if (data.state) applyRemoteState(data.state);
                    else fetchRoomState();
                    showStatusToast('상태 갱신', '다른 동작이 먼저 반영되어 최신 상태를 불러왔습니다.', 2200);
                    return;
                }
                if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);

                markRoomContact();
                clearTurnTimer();
                turnLeftSeconds = data.state?.turn_left_seconds ?? 30;
                applyRemoteState(data.state);
                const label = data.yacht_bonus > 0
                    ? `🏆 Yacht Bonus: ${CATS[i]} +${data.score}점, Yacht +${data.yacht_bonus}점`
                    : CATS[i];
                showToast(label, data.score);
                flashScoreSelection(i);
            } catch (error) {
                console.warn('score failed', error);
                showStatusToast('점수 기록 실패', error.message || '잠시 후 다시 시도해 주세요.', 2600);
                fetchRoomState();
            } finally {
                scoreRequestInFlight = false;
            }
        }

        async function leaveRoom() {
            if (!confirm('정말 나가시겠습니까?')) return;
            try {
                allowImmediateExit = true;
                stopRoomEvents();
                stopSyncPolling();
                stopRoomHeartbeat();
                clearTurnTimer();
                const payload = JSON.stringify({username, player_token: playerToken});
                fetch(`/api/rooms/${roomCode}/leave`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: payload,
                    keepalive: true,
                    cache: 'no-store',
                }).catch((e) => console.warn('leave failed (non-blocking)', e));
                localStorage.removeItem('yacht_room');
                gameOverToastShown = true;
                showStatusToast('나가기 완료', '로비로 이동합니다.', 1000);
            } catch (e) {
                console.error('Leave failed', e);
                allowImmediateExit = false;
                showStatusToast('나가기 실패', '잠시 후 다시 시도해 주세요.', 1200);
                return;
            }
            setTimeout(() => { window.location.replace('/'); }, 1000);
        }

        function passTurn() {
            const myEmpty = GameState.getMyCard().every(v => v === null);
            const oppEmpty = GameState.getOppCard().every(v => v === null);
            if (!opponentName || !isMyTurn() || GameState.getRollsLeft() !== 3 || !myEmpty || !oppEmpty) return;

            turnOwner = opponentName;
            refreshTurnUI();
            updateDice();
            updateScorecard();
            pushState();

            const toast = document.getElementById('score-toast');
            toast.innerHTML = `<div style="font-size:0.8em;">선공권을 ${escapeHtml(opponentName)}님에게 넘겼습니다</div>`;
            toast.classList.add('show');
            playTurnToastSound();
            setTimeout(() => toast.classList.remove('show'), 2000);
        }

        // --- [실시간 감정표현] ---
        let reactionSending = false;
        let lastReactionId = '';
        let reactionCursorInitialized = false;
        const reactionSeenIds = new Set();
        let reactionSoundEnabled = localStorage.getItem('yacht_reaction_sound') !== 'off';
        let reactionAudioContext = null;
        const REACTION_TONES = {
            nice: [523, 659], fire: [440, 659, 880], laugh: [392, 330, 392],
            wow: [262, 523], dice: [294, 440], gg: [523, 659, 784],
        };
        const REACTION_COOLDOWN_MS = 2000;

        function updateReactionSoundButton() {
            const button = document.getElementById('reaction-sound-toggle');
            if (!button) return;
            button.textContent = reactionSoundEnabled ? '🔊' : '🔇';
            button.setAttribute('aria-pressed', String(reactionSoundEnabled));
            button.setAttribute('aria-label', reactionSoundEnabled ? '감정표현 소리 끄기' : '감정표현 소리 켜기');
        }

        function toggleReactionSound() {
            reactionSoundEnabled = !reactionSoundEnabled;
            localStorage.setItem('yacht_reaction_sound', reactionSoundEnabled ? 'on' : 'off');
            updateReactionSoundButton();
            if (reactionSoundEnabled) playReactionSound('nice');
        }

        function playReactionSound(code) {
            if (!reactionSoundEnabled) return;
            try {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (!AudioContextClass) return;
                reactionAudioContext = reactionAudioContext || new AudioContextClass();
                if (reactionAudioContext.state === 'suspended') reactionAudioContext.resume();
                const startedAt = reactionAudioContext.currentTime;
                (REACTION_TONES[code] || REACTION_TONES.nice).forEach((frequency, index) => {
                    const oscillator = reactionAudioContext.createOscillator();
                    const gain = reactionAudioContext.createGain();
                    const noteAt = startedAt + index * 0.09;
                    oscillator.type = code === 'fire' ? 'sawtooth' : 'sine';
                    oscillator.frequency.setValueAtTime(frequency, noteAt);
                    gain.gain.setValueAtTime(0.0001, noteAt);
                    gain.gain.exponentialRampToValueAtTime(0.12, noteAt + 0.015);
                    gain.gain.exponentialRampToValueAtTime(0.0001, noteAt + 0.11);
                    oscillator.connect(gain).connect(reactionAudioContext.destination);
                    oscillator.start(noteAt);
                    oscillator.stop(noteAt + 0.12);
                });
            } catch (error) {
                console.warn('reaction sound unavailable', error);
            }
        }

        function showReaction(reaction) {
            if (!reaction || !reaction.id || reactionSeenIds.has(reaction.id)) return;
            reactionSeenIds.add(reaction.id);
            lastReactionId = reaction.id;
            reactionCursorInitialized = true;
            const layer = document.getElementById('reaction-burst-layer');
            if (!layer) return;
            const burst = document.createElement('div');
            const mine = reaction.user === username;
            burst.className = `reaction-burst ${mine ? 'mine' : 'incoming'}`;
            const label = document.createElement('span');
            label.className = 'reaction-burst-label';
            label.textContent = mine ? `내 ${reaction.label}` : `${reaction.user} · ${reaction.label}`;
            const emoji = document.createElement(reaction.asset ? 'img' : 'span');
            emoji.className = 'reaction-burst-emoji';
            if (reaction.asset) {
                emoji.src = reaction.asset;
                emoji.alt = reaction.emoji || reaction.label;
                emoji.addEventListener('error', () => {
                    const fallback = document.createElement('span');
                    fallback.className = 'reaction-burst-emoji';
                    fallback.textContent = reaction.emoji || '✨';
                    emoji.replaceWith(fallback);
                }, {once: true});
            } else {
                emoji.textContent = reaction.emoji;
            }
            burst.append(label, emoji);
            layer.appendChild(burst);
            playReactionSound(reaction.code);
            setTimeout(() => burst.remove(), 1800);
        }

        function syncReactions(reactions) {
            if (!Array.isArray(reactions)) return;
            if (!reactionCursorInitialized) {
                lastReactionId = reactions.length ? (reactions[reactions.length - 1].id || '') : '';
                reactionCursorInitialized = true;
                return;
            }
            if (reactions.length === 0) return;
            const cursor = reactions.findIndex((reaction) => reaction.id === lastReactionId);
            const pending = cursor >= 0 ? reactions.slice(cursor + 1) : reactions.slice(-1);
            pending.forEach(showReaction);
        }

        function setReactionButtonsDisabled(disabled) {
            document.querySelectorAll('[data-reaction]').forEach((button) => { button.disabled = disabled; });
        }

        async function sendReaction(reaction) {
            if (reactionSending || isObserver) return;
            reactionSending = true;
            setReactionButtonsDisabled(true);
            try {
                const r = await fetchWithTimeout(
                    `/api/rooms/${roomCode}/reaction`,
                    {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ username, player_token: playerToken, reaction }),
                    },
                    currentRoomRequestTimeoutMs(),
                );
                const data = await r.json();
                if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
                showReaction(data.reaction);
            } catch (e) {
                console.warn('reaction send failed', e);
                showStatusToast('감정표현 전송 실패', e.message || '잠시 후 다시 시도해 주세요.', 1400);
            } finally {
                setTimeout(() => {
                    reactionSending = false;
                    setReactionButtonsDisabled(false);
                }, REACTION_COOLDOWN_MS);
            }
        }

        async function initializeGame() {
            syncMobileInsightPlacement();
            if (typeof mobileInsightQuery.addEventListener === 'function') {
                mobileInsightQuery.addEventListener('change', syncMobileInsightPlacement);
            } else {
                mobileInsightQuery.addListener(syncMobileInsightPlacement);
            }
            const reactionDock = document.getElementById('reaction-dock');
            if (reactionDock && !isObserver) reactionDock.style.display = 'block';
            updateReactionSoundButton();
            renderDice();
            updateScorecard();
            document.getElementById('ai-breakdown').innerHTML = '<div style="color:#999; text-align:center; padding:12px; font-size:0.9em;">🎲 주사위를 굴려주세요</div>';
            bindAiModeControls(() => {
                if (!isObserver && !gameOver && isMyTurn() && rollsLeft < 3) askAI();
            });
            const roomLabel = document.getElementById('room-label');
            if (roomLabel) roomLabel.textContent = `Room ${roomCode}`;

            try {
                if (isObserver) {
                    await tryObserveRoom();
                }
                await fetchRoomState();
            } catch (e) {
                console.warn('Failed to fetch initial room state:', e);
            }
            startRoomEvents({immediate: false});
            startRoomHeartbeat({immediate: true});
            refreshTurnUI();
            refreshInsightPanels();
        }

        initializeGame().catch(e => console.error('Initialization error:', e));
