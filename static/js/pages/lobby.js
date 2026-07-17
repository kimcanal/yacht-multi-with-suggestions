function escapeHtml(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function roomTokenKey(code) {
            return `yacht_player_token_${code}`;
        }

        let clientId = localStorage.getItem('yacht_client_id');
        if (!clientId) {
            clientId = 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('yacht_client_id', clientId);
        }
        document.getElementById('client-id-disp').textContent = clientId.substr(-6);

        let myUsername = localStorage.getItem('yacht_username');
        let isLoggedIn = false;
        let pollingStarted = false;
        let selectedLeaderboardUser = null;
        const pollingTimers = [];

        function formatRelativeTime(isoString) {
            if (!isoString) return '-';
            const target = new Date(isoString);
            if (Number.isNaN(target.getTime())) return isoString;
            const diffSeconds = Math.max(0, Math.floor((Date.now() - target.getTime()) / 1000));
            if (diffSeconds < 60) return '방금 전';
            if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}분 전`;
            if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}시간 전`;
            return `${Math.floor(diffSeconds / 86400)}일 전`;
        }

        function renderPlayerSpotlightEmpty(message) {
            const root = document.getElementById('player-spotlight');
            if (!root) return;
            root.className = 'spotlight-card spotlight-empty';
            root.textContent = message;
        }

        function renderPlayerSpotlight(profile) {
            const root = document.getElementById('player-spotlight');
            if (!root) return;

            const streakType = profile.current_streak?.type;
            const streakCount = Number(profile.current_streak?.count || 0);
            const streakLabel = streakType === 'win'
                ? `${streakCount}연승`
                : streakType === 'loss'
                    ? `${streakCount}연패`
                    : streakType === 'draw'
                        ? `${streakCount}연속 무승부`
                        : '기록 준비 중';
            const streakClass = streakType ? `spotlight-streak ${streakType}` : 'spotlight-streak';
            const recentForm = Array.isArray(profile.recent_form) ? profile.recent_form : [];
            const formMarkup = recentForm.length
                ? recentForm.map((entry) => {
                    const normalized = entry === 'W' ? 'win' : entry === 'L' ? 'loss' : 'draw';
                    return `<span class="form-pill ${normalized}">${entry}</span>`;
                }).join('')
                : '<span style="color:var(--muted-2); font-size:0.82em;">아직 멀티 경기 기록이 없습니다.</span>';

            root.className = 'spotlight-card';
            root.innerHTML = `
                <div class="spotlight-header">
                    <div>
                        <div class="spotlight-kicker">Player Spotlight</div>
                        <div class="spotlight-name">
                            ${escapeHtml(profile.username)}
                            ${profile.rank ? `<span class="spotlight-rank">#${profile.rank}</span>` : ''}
                        </div>
                    </div>
                    <div class="${streakClass}">${streakLabel}</div>
                </div>
                <div class="spotlight-grid">
                    <div class="spotlight-metric">
                        <div class="spotlight-metric-label">전적</div>
                        <div class="spotlight-metric-value">${profile.wins}승 ${profile.draws}무 ${profile.losses}패</div>
                    </div>
                    <div class="spotlight-metric">
                        <div class="spotlight-metric-label">승률</div>
                        <div class="spotlight-metric-value">${Number(profile.win_rate || 0).toFixed(1)}%</div>
                    </div>
                    <div class="spotlight-metric">
                        <div class="spotlight-metric-label">평균 점수</div>
                        <div class="spotlight-metric-value">${Number(profile.avg_score || 0).toFixed(1)}</div>
                    </div>
                    <div class="spotlight-metric">
                        <div class="spotlight-metric-label">최근 경기</div>
                        <div class="spotlight-metric-value">${formatRelativeTime(profile.last_played_at)}</div>
                    </div>
                </div>
                <div class="spotlight-form">
                    <span class="spotlight-form-label">최근 폼</span>
                    ${formMarkup}
                </div>
            `;
        }

        function checkLogin() {
            if (myUsername && myUsername.length >= 2) {
                document.getElementById('login-overlay').style.display = 'none';
                document.getElementById('display-username').textContent = myUsername;
                isLoggedIn = true;
                selectedLeaderboardUser = myUsername;
                startPolling();
            } else {
                document.getElementById('login-overlay').style.display = 'flex';
                document.getElementById('login-username').focus();
            }
        }

        function submitLogin() {
            const name = document.getElementById('login-username').value.trim();
            const valid = /^[A-Za-z0-9가-힣_]{2,12}$/.test(name);
            if (!valid) {
                alert('닉네임은 2~12자, 한글/영문/숫자/_만 사용 가능합니다.');
                return;
            }
            myUsername = name;
            localStorage.setItem('yacht_username', name);
            document.getElementById('display-username').textContent = name;
            selectedLeaderboardUser = name;

            const overlay = document.getElementById('login-overlay');
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.display = 'none';
                isLoggedIn = true;
                sendHeartbeat();
                startPolling();
            }, 300);
        }

        function logout() {
            if(confirm('로그아웃 하시겠습니까?')) {
                localStorage.removeItem('yacht_username');
                location.reload();
            }
        }

        document.getElementById('login-username').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') submitLogin();
        });

        let currentRankMode = 'multi';

        function startGame(mode = 'solo') {
            localStorage.setItem('yacht_username', myUsername);
            localStorage.removeItem('yacht_room');
            const nextMode = mode === 'vs-ai' ? 'vs-ai' : 'solo';
            location.href = `/game/single?mode=${encodeURIComponent(nextMode)}`;
        }

        async function createRoom() {
            if(!myUsername) return;
            try {
                const res = await fetch('/api/rooms', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:myUsername})});
                const data = await res.json();
                if(data.code) {
                    if (data.player_token) localStorage.setItem(roomTokenKey(data.code), data.player_token);
                    localStorage.setItem('yacht_room', data.code);
                    location.href=`/game/multi?room=${data.code}`;
                }
            } catch(e) { alert('오류'); }
        }

        async function joinRoomById() {
            const code = document.getElementById('room-code').value.trim().toUpperCase();
            if(!code) return alert('방 코드를 입력하세요');
            try {
                const res = await fetch(`/api/rooms/${code}/join`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:myUsername})});
                const data = await res.json();
                if(res.ok) {
                    if (data.player_token) localStorage.setItem(roomTokenKey(code), data.player_token);
                    localStorage.setItem('yacht_room', code);
                    location.href=`/game/multi?room=${code}`;
                }
                else document.getElementById('error').innerText = data.error;
            } catch(e) {}
        }

        async function joinAsObserver(code) {
            const obsName = 'Guest_' + Math.floor(Math.random()*1000);
            try {
                const res = await fetch(`/api/rooms/${code}/observe`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: obsName})
                });
                if(res.ok) {
                    localStorage.setItem('yacht_username', obsName);
                    localStorage.setItem('yacht_room', code);
                    location.href = `/game/multi?room=${code}&mode=observer`;
                } else {
                    const d = await res.json();
                    alert(d.error || '실패');
                }
            } catch(e) { alert('오류'); }
        }

        function loadLobbyUsers() {
            if (!isLoggedIn) return;
            fetch('/api/online-users').then(r=>r.json()).then(users=>{
                const list = document.getElementById('lobby-user-list');
                if(!users.length) {
                    list.innerHTML = '<div class="empty-state"><div class="empty-icon">🔭</div><div class="empty-text">접속자 없음</div></div>';
                    return;
                }
                list.innerHTML = users.map(u => {
                    const rawName = (u.username && u.username !== 'undefined') ? u.username : '익명';
                    const name = escapeHtml(rawName);
                    const isMe = rawName === myUsername;
                    const nameColor = isMe ? 'var(--gold-strong)' : 'var(--mint-bright)';
                    const meLabel = isMe ? '<span style="color:var(--muted); font-size:0.8em; margin-left:4px;">(나)</span>' : '';

                    let statusBadge = '';
                    if(u.status === '게임중') statusBadge = '<span class="status-badge badge-game">게임중</span>';
                    else statusBadge = '<span class="status-badge badge-wait">대기중</span>';

                    return `
                    <div class="lobby-user-row" style="color:${nameColor}; font-weight:600; font-size:1.05em;">
                        <span class="lobby-user-dot">●</span>
                        <div class="lobby-user-name">
                            <span class="lobby-user-name-text">${name}</span>
                            ${meLabel}
                        </div>
                        <div class="lobby-user-status">${statusBadge}</div>
                    </div>`;
                }).join('');
            }).catch(()=>{});
        }

        function loadRoomList() {
            fetch('/api/rooms', {cache:'no-store'}).then(r=>r.json()).then(rooms=>{
                const list = document.getElementById('room-list');
                const waitingCount = rooms.filter((room) => (room.room_phase || (room.players.length >= 2 ? 'playing' : 'waiting')) === 'waiting').length;
                const playingCount = rooms.filter((room) => (room.room_phase || (room.players.length >= 2 ? 'playing' : 'waiting')) === 'playing').length;
                const waitingEl = document.getElementById('glance-waiting-rooms');
                const playingEl = document.getElementById('glance-playing-rooms');
                if (waitingEl) waitingEl.textContent = waitingCount;
                if (playingEl) playingEl.textContent = playingCount;
                if(!rooms.length) {
                    list.innerHTML='<div class="empty-state"><div class="empty-icon">🎲</div><div class="empty-text">대기 중인 방 없음<br>새로운 방을 생성해보세요!</div></div>';
                    return;
                }
                list.innerHTML = rooms.map(r=>{
                    const isFull = r.players.length >= 2;
                    const observerCount = Number(r.observer_count || 0);
                    const roomPhase = r.room_phase || (isFull ? 'playing' : 'waiting');
                    let pInfo = r.players.length === 0 ? '대기 중' :
                                r.players.length === 1 ? `<span style="color:var(--mint-bright)">${escapeHtml(r.players[0])}</span>` :
                                `<span style="color:var(--mint-bright)">${escapeHtml(r.players[0])}</span> vs <span style="color:var(--danger)">${escapeHtml(r.players[1])}</span>`;
                    const phaseLabel = roomPhase === 'playing' ? '진행 중' : (roomPhase === 'finished' ? '종료됨' : '대기 중');
                    const audienceBadge = observerCount > 0 ? `<span class="status-badge badge-watch">관전자 ${observerCount}</span>` : '';

                    return `
                    <div class="room-item">
                        <div class="room-meta">
                            <div class="room-code">🎮 ${escapeHtml(r.code)}</div>
                            <div class="room-players">${pInfo}</div>
                            <div class="room-badges">
                                <span class="room-phase ${escapeHtml(roomPhase)}">${phaseLabel}</span>
                                ${audienceBadge}
                            </div>
                        </div>
                        <div class="room-action">
                            ${isFull
                                ? `<button class="btn-mini" style="background:var(--orange); padding:6px 12px; font-size:0.8em;" onclick="joinAsObserver('${r.code}')">👁️ 관전</button>`
                                : `<button class="btn-mini btn-s" style="padding:6px 12px; font-size:0.8em;" onclick="joinRoom('${r.code}')">참가</button>`
                            }
                        </div>
                    </div>`;
                }).join('');
            }).catch(()=>{});
        }
        window.joinRoom = function(code) { document.getElementById('room-code').value=code; joinRoomById(); }

        function switchRank(mode) {
            currentRankMode = mode;
            document.getElementById('tab-multi').className = mode === 'multi' ? 'rank-tab active' : 'rank-tab';
            document.getElementById('tab-single').className = mode === 'single' ? 'rank-tab active' : 'rank-tab';
            loadLeaderboard();
            refreshPlayerSpotlight();
        }

        function showPlayerSpotlight(username) {
            selectedLeaderboardUser = username;
            refreshPlayerSpotlight();
            if (currentRankMode === 'multi') loadLeaderboard();
        }

        function refreshPlayerSpotlight() {
            if (!isLoggedIn) return;
            if (currentRankMode !== 'multi') {
                renderPlayerSpotlightEmpty('멀티 탭에서 선수 전적을 확인할 수 있어요.');
                return;
            }

            const target = selectedLeaderboardUser || myUsername;
            if (!target) {
                renderPlayerSpotlightEmpty('표시할 선수를 찾지 못했습니다.');
                return;
            }

            fetch(`/api/leaderboard/users/${encodeURIComponent(target)}?recent_limit=5`, {cache:'no-store'})
                .then(async (res) => {
                    if (!res.ok) {
                        const payload = await res.json().catch(() => ({}));
                        throw new Error(payload.error || '전적 조회 실패');
                    }
                    return res.json();
                })
                .then(renderPlayerSpotlight)
                .catch(() => {
                    renderPlayerSpotlightEmpty('아직 멀티 경기 기록이 없습니다.');
                });
        }

        function loadLeaderboard() {
            if (!isLoggedIn) return;
            const endpoint = currentRankMode === 'multi' ? '/api/leaderboard/multi' : '/api/leaderboard/single';
            fetch(endpoint).then(r=>r.json()).then(users=>{
                const list = document.getElementById('leaderboard-list');
                if(!users.length) {
                    if (currentRankMode === 'multi') {
                        renderPlayerSpotlightEmpty('아직 멀티 전적이 없습니다. 첫 경기를 만들어보세요.');
                    }
                    list.innerHTML='<div class="empty-state"><div class="empty-icon">🏆</div><div class="empty-text">기록 없음<br>첫 승리의 주인공이 되세요!</div></div>';
                    return;
                }
                if (currentRankMode === 'multi') {
                    const visibleUsers = users.slice(0, 20).map((u) => u.username);
                    if (!selectedLeaderboardUser || !visibleUsers.includes(selectedLeaderboardUser)) {
                        selectedLeaderboardUser = visibleUsers.includes(myUsername) ? myUsername : visibleUsers[0];
                    }
                }

                list.innerHTML = users.slice(0,20).map((u, i) => {
                    let detail = '';
                    if(currentRankMode === 'multi') detail = `${u.wins}승 ${u.losses}패`;
                    else detail = `${u.score}점`;
                    const clickableClass = currentRankMode === 'multi' ? ' clickable' : '';
                    const selectedClass = currentRankMode === 'multi' && u.username === selectedLeaderboardUser ? ' selected' : '';
                    const clickAttr = currentRankMode === 'multi'
                        ? `onclick="showPlayerSpotlight('${escapeHtml(u.username)}')"`
                        : '';

                    return `
                    <div class="leaderboard-item${clickableClass}${selectedClass}" ${clickAttr}>
                        <div style="font-weight:500; color:var(--text);"><span class="rank-badge">${i+1}</span> ${escapeHtml(u.username)}</div>
                        <div style="color:var(--muted); font-family:'Rajdhani'">${detail}</div>
                    </div>`;
                }).join('');
                if (currentRankMode === 'multi') refreshPlayerSpotlight();
            }).catch(()=>{});
        }

        function loadRecentGames() {
            if (!isLoggedIn) return;
            fetch('/api/leaderboard/recent?limit=6', {cache:'no-store'}).then(r=>r.json()).then(games=>{
                const root = document.getElementById('recent-games-list');
                if (!root) return;
                if (!Array.isArray(games) || !games.length) {
                    root.innerHTML = '<div class="empty-state"><div class="empty-icon">🕒</div><div class="empty-text">아직 저장된 경기 기록이 없습니다.<br>혼자하기나 방 생성을 눌러 첫 경기를 시작해보세요.</div></div>';
                    return;
                }

                root.innerHTML = games.map((game) => {
                    const matchup = game.player2
                        ? `${escapeHtml(game.player1)} vs ${escapeHtml(game.player2)}`
                        : `${escapeHtml(game.player1)} solo`;
                    const scoreLine = game.player2
                        ? `${game.score1} : ${game.score2}`
                        : `${game.score1}점`;
                    const winner = game.winner === 'DRAW'
                        ? '무승부'
                        : game.winner
                            ? `승자 ${escapeHtml(game.winner)}`
                            : '결과 없음';
                    return `
                        <div class="recent-game-item">
                            <div class="recent-game-top">
                                <div class="recent-matchup">${matchup}</div>
                                <div class="recent-time">${formatRelativeTime(game.timestamp)}</div>
                            </div>
                            <div class="recent-game-bottom">
                                <div class="recent-score">${scoreLine}</div>
                                <div class="recent-winner"><strong>${winner}</strong></div>
                            </div>
                        </div>
                    `;
                }).join('');
            }).catch(()=>{});
        }

        function loadSystemStatus() {
            fetch('/api/system-status').then(r=>r.json()).then(data=>{
                document.getElementById('online-count').textContent=data.online_count;
                document.getElementById('active-rooms').textContent=data.active_rooms;
                const glanceOnline = document.getElementById('glance-online-count');
                const glanceRooms = document.getElementById('glance-active-rooms');
                if (glanceOnline) glanceOnline.textContent = data.online_count;
                if (glanceRooms) glanceRooms.textContent = data.active_rooms;
                document.getElementById('cpu-bar').style.width=data.cpu_percent+'%';
                document.getElementById('memory-bar').style.width=data.memory_percent+'%';

                // 숫자도 함께 표시
                document.getElementById('cpu-usage').textContent = data.cpu_percent + '%';
                document.getElementById('memory-usage').textContent = data.memory_percent + '%';
                document.getElementById('cpu-model').textContent = data.cpu_model || '';

                // [NEW] 실제 메모리 사용량(GB)도 표시
                if (data.memory_used_gb !== undefined && data.memory_total_gb !== undefined) {
                    document.getElementById('memory-actual').textContent = `(${data.memory_used_gb}GB / ${data.memory_total_gb}GB)`;
                } else {
                    document.getElementById('memory-actual').textContent = '';
                }

                const aiAvg = Number(data.ai_recent_avg_ms || 0).toFixed(1);
                const aiP95 = Number(data.ai_recent_p95_ms || 0).toFixed(1);
                document.getElementById('ai-latency').textContent = `${aiAvg}ms avg / ${aiP95}ms p95`;
                document.getElementById('ai-cache').textContent =
                    `${data.ai_recent_samples || 0} samples · roll ${data.ai_recent_roll_count || 0} / score ${data.ai_recent_score_count || 0} · cache ${Number(data.ai_cache_hit_rate || 0).toFixed(1)}%`;

                const slowSamples = Array.isArray(data.ai_recent_slow_samples) ? data.ai_recent_slow_samples : [];
                const slowRoot = document.getElementById('ai-slow-list');
                if (slowRoot) {
                    if (!slowSamples.length) {
                        slowRoot.innerHTML = '<div style="color:var(--muted-3);">최근 느린 케이스 없음</div>';
                    } else {
                        slowRoot.innerHTML = slowSamples.slice(0, 3).map((sample) => {
                            const elapsed = Number(sample.elapsed_ms || 0).toFixed(0);
                            const stage = escapeHtml(sample.stage || 'unknown');
                            const mode = escapeHtml(sample.mode || 'focused');
                            const dice = Array.isArray(sample.dice) && sample.dice.length ? sample.dice.join(', ') : '-';
                            const target = sample.target ? ` → ${escapeHtml(sample.target)}` : '';
                            const rollsLeft = escapeHtml(sample.rolls_left ?? '-');
                            const openSlots = escapeHtml(sample.open_slots ?? '-');
                            return `
                                <div style="padding-top:6px; border-top:1px solid rgba(255,255,255,0.06);">
                                    <div><span style="color:var(--warning-soft);">${elapsed}ms</span> · ${stage} · ${mode}${target}</div>
                                    <div style="margin-top:2px; color:var(--muted-3);">[${escapeHtml(dice)}] / roll ${rollsLeft} / open ${openSlots}</div>
                                </div>
                            `;
                        }).join('');
                    }
                }
            }).catch(()=>{});
        }

        function sendHeartbeat() {
            if (!isLoggedIn) return;
            fetch('/api/lobby-heartbeat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({client_id:clientId, username:myUsername})}).catch(()=>{});
        }

        document.getElementById('room-code').addEventListener('keypress', (e) => { if(e.key === 'Enter') joinRoomById(); });

        function refreshLobbyNow() {
            loadLobbyUsers();
            loadRoomList();
            loadLeaderboard();
            loadRecentGames();
            loadSystemStatus();
            refreshPlayerSpotlight();
            sendHeartbeat();
        }

        function startPolling() {
            if (pollingStarted) return;
            pollingStarted = true;
            refreshLobbyNow();

            pollingTimers.push(setInterval(loadLobbyUsers, 3000));
            pollingTimers.push(setInterval(loadRoomList, 3000));
            pollingTimers.push(setInterval(loadLeaderboard, 5000));
            pollingTimers.push(setInterval(loadRecentGames, 5000));
            pollingTimers.push(setInterval(loadSystemStatus, 3000));
            pollingTimers.push(setInterval(refreshPlayerSpotlight, 5000));
            pollingTimers.push(setInterval(sendHeartbeat, 10000));
        }

        document.addEventListener('visibilitychange', () => {
            if (!isLoggedIn || document.visibilityState !== 'visible') return;
            refreshLobbyNow();
        });

        checkLogin();
