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

function renderAiStatus(targetId, message, tone = 'muted', detail = '') {
    const root = document.getElementById(targetId);
    if (!root) return;
    const palette = {
        muted: {
            title: '#c6d1de',
            detail: '#8fa3b8',
            border: 'rgba(255,255,255,0.08)',
            background: 'rgba(255,255,255,0.04)',
        },
        info: {
            title: '#7ef3cb',
            detail: '#adc0d2',
            border: 'rgba(126,243,203,0.2)',
            background: 'rgba(89,240,194,0.08)',
        },
        thinking: {
            title: '#9ed8ff',
            detail: '#adc0d2',
            border: 'rgba(102,217,255,0.2)',
            background: 'rgba(102,217,255,0.08)',
        },
        error: {
            title: '#ff9b9b',
            detail: '#ffc4c4',
            border: 'rgba(255,123,123,0.22)',
            background: 'rgba(255,123,123,0.08)',
        },
    };
    const selected = palette[tone] || palette.muted;
    const detailMarkup = detail
        ? `<div style="margin-top:6px; color:${selected.detail}; text-align:center; font-size:0.82em; line-height:1.5;">${escapeHtml(detail)}</div>`
        : '';
    root.innerHTML = `
        <div style="padding:12px 14px; border-radius:12px; border:1px solid ${selected.border}; background:${selected.background}; text-align:center;">
            <div style="color:${selected.title}; font-size:0.94em; font-weight:800; line-height:1.45;">${escapeHtml(message)}</div>
            ${detailMarkup}
        </div>
    `;
}
