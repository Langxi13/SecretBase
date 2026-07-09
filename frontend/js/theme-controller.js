/**
 * Theme state and auto time-based theme switching.
 */
(function () {
    function createThemeController(options) {
        const {
            ref,
            computed,
            settingsForm,
            store
        } = options;

        let autoThemeTimer = null;
        const currentTheme = ref('system');
        const themeIcon = computed(() => {
            switch (currentTheme.value) {
                case 'dark': return '🌙';
                case 'light': return '☀️';
                default: return '🕒';
            }
        });

        function resolveAutoTheme(date = new Date()) {
            const hour = date.getHours();
            return hour >= 18 || hour < 6 ? 'dark' : 'light';
        }

        function applyTheme(theme) {
            const root = document.documentElement;
            if (theme === 'system') {
                root.setAttribute('data-theme', resolveAutoTheme());
                root.setAttribute('data-theme-mode', 'auto');
            } else {
                root.setAttribute('data-theme', theme);
                root.setAttribute('data-theme-mode', theme);
            }
        }

        function applyAutoThemeIfNeeded() {
            if (currentTheme.value === 'system') {
                applyTheme('system');
            }
        }

        function startAutoThemeTimer() {
            clearAutoThemeTimer();
            autoThemeTimer = setInterval(applyAutoThemeIfNeeded, 60 * 1000);
        }

        function clearAutoThemeTimer() {
            if (!autoThemeTimer) return;
            clearInterval(autoThemeTimer);
            autoThemeTimer = null;
        }

        function toggleTheme() {
            const themes = ['system', 'light', 'dark'];
            const currentIndex = themes.indexOf(currentTheme.value);
            currentTheme.value = themes[(currentIndex + 1) % themes.length];
            settingsForm.theme = currentTheme.value;
            applyTheme(currentTheme.value);
            store.updateSettings({ theme: currentTheme.value });
        }

        return {
            currentTheme,
            themeIcon,
            toggleTheme,
            applyTheme,
            startAutoThemeTimer,
            clearAutoThemeTimer,
            resolveAutoTheme
        };
    }

    window.SecretBaseThemeController = {
        createThemeController
    };
})();
