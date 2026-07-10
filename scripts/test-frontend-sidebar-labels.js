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
    ['标签', 'sidebar-label-tags', '🏷️'],
    ['管理', 'sidebar-label-tools', '⚙️']
].forEach(([label, className, icon]) => {
    assertIncludes(markup, `class="sidebar-label ${className}"`, `${label}分组标题必须有独立语义类`);
    assertIncludes(markup, `aria-label="${label}"`, `${label}分组标题必须保留无障碍名称`);
    assertIncludes(markup, `<span class="sidebar-label-icon" aria-hidden="true">${icon}</span>`, `${label}分组标题必须使用图标`);
});

assertNotIncludes(markup, 'label-indicator', '侧边栏折叠态不应继续使用难以识别的小圆点');
assertNotIncludes(css, '.label-indicator', '旧的小圆点样式应删除，避免冗余规则');

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

console.log('PASS frontend sidebar labels');
