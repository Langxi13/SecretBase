/**
 * Auto-lock timer and activity listener wiring.
 */
(function () {
    function createAutoLockController(options) {
        const {
            settingsForm,
            locked,
            initialized,
            store,
            applyLockedState
        } = options;

        let autoLockTimer = null;
        const activityEventNames = ['click', 'keydown', 'mousemove', 'touchstart'];

        function clearAutoLockTimer() {
            if (autoLockTimer) {
                clearTimeout(autoLockTimer);
                autoLockTimer = null;
            }
        }

        function startAutoLockTimer() {
            clearAutoLockTimer();
            const minutes = Number(settingsForm.autoLockMinutes || 0);
            if (locked.value || minutes <= 0) return;

            autoLockTimer = setTimeout(async () => {
                showToast('已因长时间无操作自动锁定', 'warning');
                try {
                    await store.lock();
                } catch (error) {
                    // 即使网络请求失败，也必须立即清除前端解锁态。
                } finally {
                    applyLockedState();
                }
            }, minutes * 60 * 1000);
        }

        function resetAutoLockTimer() {
            if (!locked.value) {
                startAutoLockTimer();
            }
        }

        function bindActivityListeners() {
            activityEventNames.forEach(eventName => {
                window.addEventListener(eventName, resetAutoLockTimer, { passive: true });
            });
        }

        function unbindActivityListeners() {
            activityEventNames.forEach(eventName => {
                window.removeEventListener(eventName, resetAutoLockTimer);
            });
        }

        function handleUnauthorizedLock(event) {
            if (locked.value) return;
            showToast(event.detail?.message || '已锁定，请重新解锁', 'warning');
            applyLockedState();
        }

        return {
            startAutoLockTimer,
            clearAutoLockTimer,
            resetAutoLockTimer,
            bindActivityListeners,
            unbindActivityListeners,
            handleUnauthorizedLock
        };
    }

    window.SecretBaseAutoLock = {
        createAutoLockController
    };
})();
