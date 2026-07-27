/* Network boundary for the lobby page. */
(function attachLobbyApi(global) {
    async function request(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json().catch(() => ({}));
        return {response, data};
    }

    async function json(url, options = {}) {
        const {response, data} = await request(url, options);
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        return data;
    }

    global.LobbyApi = {
        request,
        json,
        createRoom: (username) => request('/api/rooms', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username}),
        }),
        joinRoom: (code, username) => request(`/api/rooms/${encodeURIComponent(code)}/join`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username}),
        }),
        observeRoom: (code, username) => request(`/api/rooms/${encodeURIComponent(code)}/observe`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username}),
        }),
        heartbeat: (clientId, username) => request('/api/lobby-heartbeat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({client_id: clientId, username}),
        }),
        snapshot: (query) => json(`/api/lobby-snapshot?${query.toString()}`, {cache: 'no-store'}),
    };
}(window));
