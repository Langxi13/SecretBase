const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const { readFrontendMarkup, readFrontendCss } = require('./frontend-source');

const indexHtml = readFrontendMarkup();
const appJs = read('frontend/js/app.js');
const appUiControllerJs = read('frontend/js/app-ui-controller.js');
const viewHelpersJs = read('frontend/js/view-helpers.js');
const styleCss = readFrontendCss();

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

assertIncludes(indexHtml, 'entry.fields.slice(0, 2)', '条目卡片必须继续限制字段数量，保持列表可扫描');
assertIncludes(indexHtml, 'entry.fields.length > 2', '字段超过展示数量时必须显示剩余字段提示');
assertIncludes(indexHtml, 'field-overflow-hint', '字段剩余提示必须使用专用样式');
assertIncludes(indexHtml, '还有 {{ entry.fields.length - 2 }} 个字段，点击查看详情', '字段剩余提示必须明确展示剩余数量和详情入口');
assertIncludes(indexHtml, '?v=20260710-ui-v73', '前端资源版本必须随模块拆分更新，避免浏览器继续使用旧 JS');
assertIncludes(indexHtml, ':style="entryCardStyle(entry)"', '条目卡片必须通过标签或密码组颜色注入视觉区分变量');
assertIncludes(indexHtml, 'visibleEntryGroups(entry)', '条目卡片必须控制密码组 chip 展示数量');
assertIncludes(indexHtml, 'remainingEntryGroupsCount(entry)', '密码组较多时必须显示剩余数量提示');
assertIncludes(indexHtml, 'group-chip-more', '剩余密码组提示必须使用专用 chip 样式');
assertIncludes(appUiControllerJs, 'entryCardStyle: viewHelpers.entryCardStyle', '模板上下文必须复用条目卡片视觉辅助');
assertIncludes(viewHelpersJs, 'function entryAccentColor', '条目卡片必须根据密码组或标签计算强调色');
assertIncludes(viewHelpersJs, 'function remainingEntryGroupsCount', '条目卡片必须计算剩余密码组数量');

assertMatches(
    styleCss,
    /\.field-overflow-hint\s*\{[\s\S]*?border:[\s\S]*?display:\s*flex[\s\S]*?font-size:\s*var\(--font-size-xs\)/,
    '字段剩余提示必须是轻量、可扫描的卡片内提示条'
);

assertMatches(
    styleCss,
    /\.entry-card[\s\S]*?--entry-accent[\s\S]*?border-left:[\s\S]*?var\(--entry-accent\)[\s\S]*?background:[\s\S]*?color-mix\(in srgb, var\(--entry-accent\) 5%, var\(--bg-card\)\)/,
    '条目卡片必须有静态可见的左侧色线和轻量 tint 背景'
);

assertMatches(
    styleCss,
    /\.group-chip[\s\S]*?--chip-accent[\s\S]*?border:[\s\S]*?var\(--chip-accent\)[\s\S]*?background:[\s\S]*?var\(--chip-accent\)/,
    '密码组 chip 必须用组色区分不同密码组'
);

console.log('PASS frontend card field overflow');
