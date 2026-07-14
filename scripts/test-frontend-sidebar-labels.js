const { readFrontendMarkup, readFrontendCss } = require('./frontend-source');

const markup = readFrontendMarkup();
const css = readFrontendCss();

function assertIncludes(content, needle, message) {
    if (!content.includes(needle)) {
        throw new Error(message);
    }
}

function assertNotIncludes(content, needle, message) {
    if (content.includes(needle)) {
        throw new Error(message);
    }
}

function assertMatches(content, pattern, message) {
    if (!pattern.test(content)) {
        throw new Error(message);
    }
}

[
    ['视图', 'sidebar-label-view', '▦'],
    ['标签', 'sidebar-label-tags', '🏷️']
].forEach(([label, className, icon]) => {
    assertIncludes(markup, `class="sidebar-label ${className}"`, `${label}分组标题必须有独立语义类`);
    assertIncludes(markup, `aria-label="${label}"`, `${label}分组标题必须保留无障碍名称`);
    assertIncludes(markup, `<span class="sidebar-label-icon" aria-hidden="true">${icon}</span>`, `${label}分组标题必须使用图标`);
});

assertNotIncludes(markup, 'label-indicator', '侧边栏折叠态不应继续使用难以识别的小圆点');
assertNotIncludes(css, '.label-indicator', '旧的小圆点样式应删除，避免冗余规则');
assertNotIncludes(markup, 'sidebar-tools', '左侧栏不应保留与顶部和底部重复的管理区域');
assertNotIncludes(markup, 'aria-label="管理工具"', '左侧栏管理入口应整组移除');
assertNotIncludes(css, '.sidebar-tools', '左侧栏管理区域样式应同步删除');
assertIncludes(markup, 'class="sidebar-nav-item sidebar-ai-entry" :class="{ active: showAiAssistant }"', 'AI 管家入口必须使用与普通导航一致的打开态');
assertMatches(
    css,
    /\.sidebar-ai-entry\s*\{[\s\S]*?margin:\s*0;/,
    'AI 管家入口不得使用额外外边距破坏侧栏对齐'
);

assertMatches(
    css,
    /\.sidebar-label-icon\s*\{[\s\S]*?flex:\s*0\s+0\s+26px[\s\S]*?width:\s*26px[\s\S]*?height:\s*26px[\s\S]*?font-size:\s*22px/,
    '展开态分组图标必须保持稳定尺寸'
);

assertMatches(
    css,
    /\.sidebar-label-tags\s+\.sidebar-label-icon\s*\{[\s\S]*?font-size:\s*28px/,
    '标签分组图标必须明显大于更多标签的普通导航图标'
);

assertMatches(
    css,
    /\.app-container\.sidebar-collapsed\s+\.sidebar-label\s*\{[\s\S]*?width:\s*42px[\s\S]*?height:\s*42px[\s\S]*?margin:\s*10px\s+auto\s+6px[\s\S]*?border:\s*1px\s+solid[\s\S]*?background:\s*color-mix/,
    '折叠态分组图标必须放在可见的稳定容器中'
);

assertMatches(
    css,
    /\.app-container\.sidebar-collapsed\s+\.sidebar-label-icon\s*\{[\s\S]*?width:\s*30px[\s\S]*?height:\s*30px[\s\S]*?font-size:\s*26px/,
    '折叠态分组图标必须提高可识别性'
);

assertMatches(
    css,
    /\.app-container\.sidebar-collapsed\s+\.sidebar-label-tags\s+\.sidebar-label-icon\s*\{[\s\S]*?font-size:\s*32px/,
    '折叠态标签分组图标必须保持最高识别度'
);

assertMatches(
    css,
    /@media\s*\(min-width:\s*1181px\)\s*and\s*\(max-height:\s*720px\)[\s\S]*?\.sidebar-tags\s+\.sidebar-nav-item[\s\S]*?min-height:\s*34px/,
    '短高度桌面窗口必须压缩侧栏密度，避免常用标签被挤出可视区域'
);

console.log('PASS frontend sidebar labels');
