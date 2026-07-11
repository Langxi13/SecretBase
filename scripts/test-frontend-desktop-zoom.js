const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/js/desktop-zoom-indicator.js'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'frontend/css/desktop-components.css'), 'utf8');
const indexHtml = fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8');

function createRuntime(mode) {
    const listeners = new Map();
    const elements = new Map();
    const timers = new Map();
    let nextTimerId = 1;

    function createClassList() {
        const values = new Set();
        return {
            add(value) { values.add(value); },
            remove(value) { values.delete(value); },
            contains(value) { return values.has(value); }
        };
    }

    const document = {
        body: {
            appendChild(element) {
                element.isConnected = true;
                elements.set(element.id, element);
            }
        },
        createElement() {
            const attributes = new Map();
            return {
                id: '',
                className: '',
                classList: createClassList(),
                isConnected: false,
                textContent: '',
                setAttribute(name, value) { attributes.set(name, String(value)); },
                getAttribute(name) { return attributes.get(name); }
            };
        },
        getElementById(id) {
            return elements.get(id) || null;
        }
    };

    const window = {
        SECRETBASE_RUNTIME_CONFIG: { mode },
        addEventListener(name, handler) { listeners.set(name, handler); },
        clearTimeout(id) { timers.delete(id); },
        setTimeout(callback, delay) {
            const id = nextTimerId++;
            timers.set(id, { callback, delay });
            return id;
        }
    };
    window.window = window;

    vm.runInContext(source, vm.createContext({ window, document, Number, Math }));
    return { listeners, elements, timers };
}

const desktop = createRuntime('desktop');
const zoomListener = desktop.listeners.get('secretbase:desktop-zoom-changed');
if (typeof zoomListener !== 'function') throw new Error('桌面模式没有注册缩放比例监听器');

zoomListener({ detail: { percent: 110.4 } });
const indicator = desktop.elements.get('secretbase-desktop-zoom-indicator');
if (!indicator || indicator.textContent !== '110%') throw new Error('缩放比例没有正确取整显示');
if (!indicator.classList.contains('is-visible') || indicator.getAttribute('aria-hidden') !== 'false') {
    throw new Error('缩放比例提示没有进入可见状态');
}
if (desktop.timers.size !== 1 || [...desktop.timers.values()][0].delay !== 1200) {
    throw new Error('缩放比例提示没有使用 1.2 秒隐藏延时');
}

zoomListener({ detail: { percent: 90 } });
if (indicator.textContent !== '90%' || desktop.timers.size !== 1) {
    throw new Error('连续缩放没有复用提示并重置隐藏计时');
}
const hideTimer = [...desktop.timers.values()][0];
hideTimer.callback();
if (indicator.classList.contains('is-visible') || indicator.getAttribute('aria-hidden') !== 'true') {
    throw new Error('缩放比例提示没有自动隐藏');
}

zoomListener({ detail: { percent: 900 } });
if (indicator.textContent !== '90%') throw new Error('超出范围的缩放比例不应更新提示');

const server = createRuntime('server');
if (server.listeners.has('secretbase:desktop-zoom-changed')) {
    throw new Error('服务端模式不应注册桌面缩放提示');
}

if (!styles.includes('.desktop-zoom-indicator.is-visible')) throw new Error('缩放提示可见样式缺失');
if (!indexHtml.includes('js/desktop-zoom-indicator.js?v=20260711-ui-v78')) {
    throw new Error('入口页没有加载桌面缩放提示脚本');
}

console.log('PASS frontend desktop zoom indicator');
