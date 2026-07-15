/**
 * 桌面壳锁定切换期间的敏感内容保护层。
 */
(function () {
    function clear() {
        document.documentElement.removeAttribute('data-secretbase-desktop-locking');
    }

    function scheduleRelease() {
        let scheduled = false;
        if (typeof window.requestAnimationFrame === 'function') {
            window.requestAnimationFrame(clear);
            scheduled = true;
        }
        if (typeof window.setTimeout === 'function') {
            window.setTimeout(clear, 250);
            scheduled = true;
        }
        if (!scheduled) {
            Promise.resolve().then(clear);
        }
    }

    window.SecretBaseDesktopLockCover = { clear, scheduleRelease };
})();
