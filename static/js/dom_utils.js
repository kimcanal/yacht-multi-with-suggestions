/**
 * static/js/dom_utils.js
 * 공통 DOM 유틸리티
 */

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function renderAiStatus(targetId, message, tone = 'muted') {
    const root = document.getElementById(targetId);
    if (!root) return;
    const color = tone === 'error' ? '#ff7b7b' : '#999';
    root.innerHTML = `<div style="color:${color}; text-align:center; padding:12px; font-size:0.9em;">${escapeHtml(message)}</div>`;
}
