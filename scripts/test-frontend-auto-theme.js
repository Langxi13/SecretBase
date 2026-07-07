const fs = require('fs');
const path = require('path');
const vm = require('vm');

const projectRoot = path.resolve(__dirname, '..');
const appPath = path.join(projectRoot, 'frontend/js/app.js');
const indexPath = path.join(projectRoot, 'frontend/index.html');
const systemCssPath = path.join(projectRoot, 'frontend/css/themes/system.css');

const appSource = fs.readFileSync(appPath, 'utf8');
const indexSource = fs.readFileSync(indexPath, 'utf8');

if (!appSource.includes("default: return '🕒';")) {
    throw new Error('Auto time theme should keep its own clock icon');
}

const resolverMatch = appSource.match(/function resolveAutoTheme\(date = new Date\(\)\) \{[\s\S]*?\n        \}/);
if (!resolverMatch) {
    throw new Error('resolveAutoTheme function not found');
}

const resolveAutoTheme = vm.runInNewContext(`(${resolverMatch[0]})`);

const cases = [
    ['05:59 uses dark theme', new Date('2026-07-08T05:59:00'), 'dark'],
    ['06:00 uses light theme', new Date('2026-07-08T06:00:00'), 'light'],
    ['17:59 uses light theme', new Date('2026-07-08T17:59:00'), 'light'],
    ['18:00 uses dark theme', new Date('2026-07-08T18:00:00'), 'dark']
];

for (const [name, date, expected] of cases) {
    const actual = resolveAutoTheme(date);
    if (actual !== expected) {
        throw new Error(`${name}: expected ${expected}, got ${actual}`);
    }
}

if (appSource.includes('matchMedia')) {
    throw new Error('Old system color-scheme matchMedia logic should not remain in app.js');
}

if (indexSource.includes('system.css')) {
    throw new Error('index.html should not load the removed system.css file');
}

if (fs.existsSync(systemCssPath)) {
    throw new Error('frontend/css/themes/system.css should be removed');
}

console.log('PASS frontend auto theme');
