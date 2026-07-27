/* Pure display helpers shared by the lobby controller. */
(function attachLobbyRender(global) {
    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

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

    global.LobbyRender = {escapeHtml, formatRelativeTime};
}(window));
