/**
 * WebDAV 自动同步计时器、前后台监听与解锁会话边界。
 */
(function () {
    function createSyncLifecycle({ state, runSync }) {
        let autoSyncTimer = null;
        let hiddenAt = 0;
        let active = false;
        let listenersBound = false;
        let epoch = 0;

        function currentEpoch() {
            return epoch;
        }

        function epochIsCurrent(value) {
            return value === epoch;
        }

        function responseBelongsToCurrentSession(value) {
            return active && epochIsCurrent(value);
        }

        function isActive() {
            return active;
        }

        function clearTimer() {
            if (autoSyncTimer !== null) {
                window.clearTimeout(autoSyncTimer);
                autoSyncTimer = null;
            }
        }

        function schedule(delay = 5000) {
            if (!active || !state.syncStatus.configured || state.syncStatus.auto_sync === false) return;
            if (state.syncStatus.phase === 'conflict') return;
            clearTimer();
            autoSyncTimer = window.setTimeout(() => {
                autoSyncTimer = null;
                runSync({ silent: true });
            }, Math.max(0, delay));
        }

        function handleVaultMutation() {
            schedule(5000);
        }

        function handleVisibilityChange() {
            if (document.hidden) {
                hiddenAt = Date.now();
                return;
            }
            if (hiddenAt && Date.now() - hiddenAt >= 60000) schedule(0);
            hiddenAt = 0;
        }

        function bindListeners() {
            if (listenersBound) return;
            window.addEventListener('secretbase:vault-mutated', handleVaultMutation);
            document.addEventListener('visibilitychange', handleVisibilityChange);
            listenersBound = true;
        }

        async function initialize({ loadStatus, loadConflicts }) {
            active = true;
            bindListeners();
            const activationEpoch = epoch;
            const status = await loadStatus({ silent: true });
            if (!responseBelongsToCurrentSession(activationEpoch) || !status) return;
            if (state.syncStatus.phase === 'conflict') await loadConflicts(true);
            else schedule(0);
        }

        function pause() {
            active = false;
            epoch += 1;
            hiddenAt = 0;
            clearTimer();
        }

        function dispose() {
            pause();
            if (!listenersBound) return;
            window.removeEventListener('secretbase:vault-mutated', handleVaultMutation);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            listenersBound = false;
        }

        return {
            currentEpoch,
            epochIsCurrent,
            responseBelongsToCurrentSession,
            isActive,
            clearTimer,
            schedule,
            initialize,
            pause,
            dispose
        };
    }

    window.SecretBaseSyncLifecycle = { createSyncLifecycle };
})();
