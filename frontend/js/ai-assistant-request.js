/**
 * AI 管家请求生命周期的小型适配器。
 * 统一处理用户取消和会话清理，避免控制器遗留“处理中”状态。
 */
(function () {
    function createAiAssistantRequestLifecycle() {
        let controller = null;
        function begin() {
            controller = typeof AbortController === 'undefined' ? null : new AbortController();
            return controller;
        }
        function finish(requestController) {
            if (controller === requestController) controller = null;
        }
        function abort() {
            const current = controller;
            controller = null;
            try { current?.abort(); } catch (_) {}
        }
        return { begin, finish, abort, hasActive: () => Boolean(controller) };
    }

    window.SecretBaseAiAssistantRequest = { createAiAssistantRequestLifecycle };
})();
