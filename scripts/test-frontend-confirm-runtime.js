const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/app-ui-controller.js'), 'utf8');

function ref(value) {
    return { value };
}

const sandbox = { window: {} };
sandbox.window.window = sandbox.window;
vm.runInContext(source, vm.createContext(sandbox));

const state = {
    selectedSearchScopes: ref([]),
    defaultSearchScopes: [],
    entryForm: { fields: [] },
    newTag: ref(''),
    newGroup: ref(''),
    newGroupDescription: ref(''),
    selectedTemplate: ref(''),
    confirmTitle: ref(''),
    confirmMessage: ref(''),
    confirmSubmitting: ref(false),
    showConfirm: ref(false)
};

const controller = sandbox.window.SecretBaseAppUiController.createAppUiController({
    state,
    store: { setFilter() {} },
    viewHelpers: {}
});

(async () => {
    let finish;
    let calls = 0;
    controller.showConfirmDialog('删除', '确认删除？', () => {
        calls += 1;
        return new Promise(resolve => { finish = resolve; });
    });

    const first = controller.confirmAction();
    const second = controller.confirmAction();
    await Promise.resolve();
    if (calls !== 1 || !state.confirmSubmitting.value || !state.showConfirm.value) {
        throw new Error('确认操作没有阻止重复提交或错误关闭弹窗');
    }

    finish();
    await Promise.all([first, second]);
    if (state.confirmSubmitting.value || state.showConfirm.value) {
        throw new Error('确认操作完成后没有恢复交互状态');
    }

    controller.showConfirmDialog('取消', '确认取消？', () => {});
    controller.cancelConfirmAction();
    if (state.showConfirm.value) {
        throw new Error('取消确认没有关闭弹窗');
    }

    console.log('PASS frontend confirm interaction');
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
