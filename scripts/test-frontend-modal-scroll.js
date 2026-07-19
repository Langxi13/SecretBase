const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { templatePaths } = require('./frontend-source');
const css = read('frontend/css/modal-layout.css');
const inspectorCss = read('frontend/css/ai-entry-inspector.css');
const sendReviewCss = read('frontend/css/ai-send-review.css');
const markup = templatePaths.map(read).join('\n');

function assert(condition, message) {
    if (!condition) throw new Error(message);
}

assert(
    /\.modal-content\s*\{[\s\S]*?display:\s*flex[\s\S]*?flex-direction:\s*column[\s\S]*?overflow:\s*hidden/.test(css),
    '弹窗容器必须使用纵向弹性布局，并由正文承担滚动'
);
assert(
    /\.modal-content\s*>\s*form[\s\S]*?display:\s*flex[\s\S]*?min-height:\s*0[\s\S]*?overflow:\s*hidden/.test(css),
    '直接承载弹窗正文的 form 必须参与弹性布局并允许正文收缩'
);
assert(
    /\.modal-content\s*>\s*form\s*>\s*\.modal-body[\s\S]*?flex:\s*1 1 auto[\s\S]*?overflow-y:\s*auto/.test(css),
    '表单弹窗正文必须独立滚动'
);
assert(
    /\.modal-content\s*>\s*\.modal-body[\s\S]*?flex:\s*1 1 auto[\s\S]*?overflow-y:\s*auto/.test(css),
    '普通弹窗正文必须独立滚动'
);
assert(
    /\.modal-header,[\s\S]*?\.modal-footer\s*\{[\s\S]*?position:\s*static/.test(css),
    '弹窗头部和底部操作栏不能覆盖正文滚动区域'
);
assert(
    /\.tag-manager-list-panel\s+\.tag-manager-list[\s\S]*?flex:\s*1 1 auto/.test(css),
    '标签管理列表必须占据剩余高度并可滚动'
);
assert(
    /\.ai-scope-entry-list[\s\S]*?overflow-y:\s*auto/.test(css),
    'AI 范围条目列表必须可滚动'
);
assert(
    /@media \(max-width:\s*767px\)[\s\S]*?\.modal-content\s*\{[\s\S]*?height:\s*100%[\s\S]*?max-height:\s*100dvh/.test(css),
    '窄屏弹窗必须使用可视区域高度，正文滚动时底部操作仍可访问'
);
assert(
    /\.ai-entry-target-list\s*\{[\s\S]*?overflow-y:\s*auto/.test(inspectorCss),
    'AI 建议关联条目列表必须独立滚动'
);
assert(
    /@media \(max-width:\s*820px\)[\s\S]*?\.ai-entry-target-panel\s*\{[\s\S]*?max-height:/.test(inspectorCss),
    '移动端 AI 条目查看层必须限制目标列表高度，避免挤压详情区域'
);
assert(
    /\.ai-send-review\s*\{[\s\S]*?max-height:[\s\S]*?overflow-y:\s*auto/.test(sendReviewCss),
    'AI 发送确认层内容较长时必须可以滚动到操作按钮'
);

for (const marker of [
    'sync-setup-modal',
    'sync-config-modal',
    'sync-delete-modal',
    'prompt-modal',
    'tag-browser-modal',
    'group-entry-picker-modal',
    'desktop-status-modal',
    'ai-scope-picker-modal'
]) {
    assert(markup.includes(`modal-content ${marker}`), `${marker} 必须保留弹窗结构`);
}
assert(markup.includes('class="ai-send-review"'), 'AI 发送确认层必须保留可滚动内容结构');
assert(
    (markup.match(/<form[\s\S]*?<div class="modal-body/g) || []).length >= 4,
    '同步和通用输入弹窗必须覆盖表单正文滚动回归场景'
);

console.log('PASS frontend modal scroll contract');
