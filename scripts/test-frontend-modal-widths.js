const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup, readFrontendCss } = require('./frontend-source');

const indexHtml = readFrontendMarkup();
const componentsCss = readFrontendCss();

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertMatches(content, pattern, message) {
    if (!pattern.test(content)) {
        throw new Error(message);
    }
}

assertIncludes(indexHtml, 'modal-content entry-detail-modal', '条目详情弹窗必须使用更宽的详情弹窗样式');
assertIncludes(indexHtml, 'modal-content entry-editor-modal', '新建/编辑条目弹窗必须使用更宽的编辑弹窗样式');
assertIncludes(indexHtml, 'modal-content ai-assistant-modal', 'AI 助手弹窗必须使用更宽的内容弹窗样式');
assertIncludes(indexHtml, 'modal-content trash-modal', '回收站弹窗必须使用更宽的列表弹窗样式');

assertMatches(
    indexHtml,
    /<!-- 条目详情弹窗 -->[\s\S]*?class="modal-content entry-detail-modal"/,
    '条目详情弹窗 class 不能放错位置'
);

assertMatches(
    indexHtml,
    /<!-- 创建\/编辑条目弹窗 -->[\s\S]*?class="modal-content entry-editor-modal"/,
    '新建/编辑条目弹窗 class 不能放错位置'
);

assertMatches(
    indexHtml,
    /<!-- AI 智能录入弹窗 -->[\s\S]*?class="modal-content ai-assistant-modal"/,
    'AI 助手弹窗 class 不能放错位置'
);

assertMatches(
    indexHtml,
    /<!-- 回收站弹窗 -->[\s\S]*?class="modal-content trash-modal"/,
    '回收站弹窗 class 不能放错位置'
);

assertMatches(
    componentsCss,
    /\.entry-editor-modal,\s*\.ai-assistant-modal[\s\S]*?max-width:\s*min\(1040px,\s*calc\(100vw - 72px\)\)/,
    '编辑条目和 AI 助手弹窗桌面端最大宽度必须提升到 1040px'
);

assertMatches(
    componentsCss,
    /\.entry-detail-modal[\s\S]*?max-width:\s*min\(920px,\s*calc\(100vw - 72px\)\)/,
    '条目详情弹窗桌面端最大宽度必须提升到 920px'
);

assertMatches(
    componentsCss,
    /\.trash-modal[\s\S]*?max-width:\s*min\(860px,\s*calc\(100vw - 72px\)\)/,
    '回收站弹窗桌面端最大宽度必须提升到 860px'
);

console.log('PASS frontend modal widths');
