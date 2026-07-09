/**
 * 将状态、派生视图与领域操作展平为 Vue 模板上下文。
 */
(function () {
    function createTemplateContext({ state, views, actions, ui, theme, data, session }) {
        return Object.assign(
            {},
            state,
            views,
            ui,
            theme,
            data,
            session,
            actions
        );
    }

    window.SecretBaseTemplateContext = {
        createTemplateContext
    };
})();
