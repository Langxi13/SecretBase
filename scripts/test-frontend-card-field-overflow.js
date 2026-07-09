const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

const indexHtml = read('frontend/index.html');
const styleCss = read('frontend/css/style.css');

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

assertIncludes(indexHtml, 'entry.fields.slice(0, 3)', '条目卡片必须继续只展示前三个字段，保持列表可扫描');
assertIncludes(indexHtml, 'entry.fields.length > 3', '字段超过三个时必须显示剩余字段提示');
assertIncludes(indexHtml, 'field-overflow-hint', '字段剩余提示必须使用专用样式');
assertIncludes(indexHtml, '还有 {{ entry.fields.length - 3 }} 个字段，点击查看详情', '字段剩余提示必须明确展示剩余数量和详情入口');
assertIncludes(indexHtml, '?v=20260709-ui-v52', '前端资源版本必须随 AI 交互标题修复更新，避免浏览器继续使用旧 JS/CSS');

assertMatches(
    styleCss,
    /\.field-overflow-hint\s*\{[\s\S]*?border:[\s\S]*?display:\s*flex[\s\S]*?font-size:\s*var\(--font-size-xs\)/,
    '字段剩余提示必须是轻量、可扫描的卡片内提示条'
);

console.log('PASS frontend card field overflow');
