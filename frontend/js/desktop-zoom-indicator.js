/** Windows 桌面原生缩放比例提示。 */
(function () {
    const runtimeConfig = window.SECRETBASE_RUNTIME_CONFIG || {};
    if (runtimeConfig.mode !== 'desktop') return;

    const indicatorId = 'secretbase-desktop-zoom-indicator';
    const displayDurationMs = 1200;
    let indicator = null;
    let hideTimer = null;

    function ensureIndicator() {
        if (indicator && indicator.isConnected !== false) return indicator;
        indicator = document.getElementById(indicatorId);
        if (indicator) return indicator;
        if (!document.body) return null;

        indicator = document.createElement('div');
        indicator.id = indicatorId;
        indicator.className = 'desktop-zoom-indicator';
        indicator.setAttribute('role', 'status');
        indicator.setAttribute('aria-live', 'polite');
        indicator.setAttribute('aria-atomic', 'true');
        indicator.setAttribute('aria-hidden', 'true');
        document.body.appendChild(indicator);
        return indicator;
    }

    function showZoomPercent(rawPercent) {
        const percent = Math.round(Number(rawPercent));
        if (!Number.isFinite(percent) || percent < 25 || percent > 500) return;

        const element = ensureIndicator();
        if (!element) return;
        element.textContent = `${percent}%`;
        element.setAttribute('aria-hidden', 'false');
        element.classList.add('is-visible');

        if (hideTimer !== null) window.clearTimeout(hideTimer);
        hideTimer = window.setTimeout(() => {
            element.classList.remove('is-visible');
            element.setAttribute('aria-hidden', 'true');
            hideTimer = null;
        }, displayDurationMs);
    }

    window.addEventListener('secretbase:desktop-zoom-changed', event => {
        showZoomPercent(event.detail && event.detail.percent);
    });
})();
