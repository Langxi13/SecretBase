# SecretBase 前端设计文档

## 0. 文档状态与阶段边界

本文档定义前端目标交互和实现边界。SecretBase 当前采用 Vue 3 CDN 单页应用，不引入构建步骤。

| 阶段 | 前端实现目标 |
|------|--------------|
| V1 | `index.html` 内联模板 + `js/app.js` 统一状态和事件逻辑，完成核心页面和操作；支持 Windows 本地直连后端和 Ubuntu 生产 `/api` 代理 |
| V1.1 | 补齐批量操作 UI、导入导出 UI、AI 智能录入、首次引导、自动锁定提醒 |
| V2 | 已完成 token 存储安全适配；PC/移动端布局分层优化已完成并通过手动确认；组件拆分或构建式 Vue 迁移暂缓，后续单独计划 |

V2.0 只调整认证 token 存储：前端使用 `sessionStorage`，不再使用 `localStorage` 长期保存 token。V2.3 前的页面重构采用“布局分层、逻辑复用”的低风险方案：PC 端增加桌面侧边栏和卡片工作台，移动端继续使用现有单列卡片流；不引入 npm 构建链，不拆 Vue SFC。该布局分层已在 Windows 本地浏览器完成手动确认。

生产环境启用 nginx Basic Auth 后，前端不得再用 HTTP `Authorization` 头传 SecretBase session token，避免覆盖浏览器 Basic Auth 认证头。前端应用 token 使用 `X-SecretBase-Token`，后端保持对旧 `Authorization: Bearer ...` 的兼容读取。

### 0.1 PC/移动端布局策略

- PC 和移动端复用同一套 API、状态、表单、弹窗和业务方法。
- PC 端允许拥有独立桌面骨架，包括左侧导航、标签筛选、管理入口和更宽的卡片工作台。
- 移动端保留顶部导航、搜索筛选、单列卡片和底部操作栏，避免把桌面密集布局压缩到手机。
- 不使用 User-Agent 分流；通过 CSS media query 控制桌面侧边栏和移动布局。
- 高级筛选在 PC 端采用等高分组卡片，保留多标签、无标签、创建时间、有/无网址、有/无备注和常用筛选；更新时间范围入口已移除以降低界面复杂度，旧更新时间筛选状态会在应用高级筛选时清空。
- 标签合并源标签输入支持中英文逗号、回车和 Tab 锁定 chip，与高级筛选标签输入保持一致。
- 设置和工具弹窗在 PC 端使用宽屏分组布局；备份管理使用独立备份中心，长文件名允许换行。
- 完全组件化、构建式 Vue 迁移、虚拟滚动继续作为后续单独任务，不混入本次布局优化。

## 1. 概述

本文档描述 SecretBase 前端的技术架构、组件设计、主题系统和移动端适配方案。

### 技术栈

- **框架**: Vue 3 (CDN，无构建步骤)
- **样式**: 原生 CSS + CSS 变量
- **图标**: 内置 SVG 图标
- **HTTP**: Fetch API

## 2. 文件结构

### 2.1 V1 当前结构

```
frontend/
├── index.html              # 主页面和 Vue 模板
├── css/
│   ├── style.css           # 基础布局和页面样式
│   ├── components.css      # 弹窗、表单、卡片、Toast 等组件样式
│   └── themes/
│       ├── variables.css   # CSS 变量定义
│       ├── dark.css        # 暗色主题
│       ├── light.css       # 亮色主题
│       └── system.css      # 跟随系统
└── js/
    ├── app.js              # Vue 应用入口、状态、页面方法
    ├── api.js              # Fetch API 封装，Windows 开发直连后端，生产环境使用 /api 前缀
    ├── store.js            # API 调用和轻量状态管理
    └── utils.js            # 工具函数、Toast、复制、favicon、日期格式化
```

### 2.2 V2 目标组件结构

以下结构是 V2 重构目标，不是 V1 必须实现：

```
frontend/
├── index.html              # 主页面
├── css/
│   ├── style.css           # 基础样式
│   ├── components.css      # 组件样式
│   └── themes/
│       ├── variables.css   # CSS 变量定义
│       ├── dark.css        # 暗色主题
│       ├── light.css       # 亮色主题
│       └── system.css      # 跟随系统
└── js/
    ├── app.js              # Vue 应用入口
    ├── api.js              # API 调用封装
    ├── store.js            # 状态管理
    ├── router.js           # 页面路由（V2 可选）
    ├── utils.js            # 工具函数
    └── components/
        ├── Header.js       # 顶部导航
        ├── Sidebar.js      # 侧边栏（桌面端）
        ├── BottomNav.js    # 底部导航（移动端）
        ├── EntryList.js    # 条目列表
        ├── EntryCard.js    # 条目卡片
        ├── EntryForm.js    # 条目表单
        ├── Pagination.js   # 分页组件
        ├── SearchBar.js    # 搜索栏
        ├── TagFilter.js    # 标签筛选
        ├── Trash.js        # 回收站
        ├── TagManager.js   # 标签管理
        ├── Settings.js     # 设置页面
        ├── AiParse.js      # AI 智能录入
        ├── ImportExport.js # 导入导出
        ├── LockScreen.js   # 锁定屏幕
        └── Toast.js        # 提示消息
```

## 3. Vue 应用结构

### 3.0 API 地址策略

前端必须支持两种运行环境：

| 环境 | 前端访问方式 | API Base URL |
|------|--------------|--------------|
| Windows 本地开发 | 静态服务，如 `http://127.0.0.1:8000` 或 `file://` | `http://127.0.0.1:10004` |
| Ubuntu 生产 | nginx 静态站点 | `/api` |

如需覆盖默认值，可在加载 `js/api.js` 之前设置：

```html
<script>
  window.SECRETBASE_API_BASE_URL = 'http://127.0.0.1:10004';
</script>
```

后端 API 使用 snake_case。前端状态可以使用 camelCase，但必须在 `store.js` 或 API 边界完成字段映射。

当前设置页的“数据迁移 / 导入导出”区提供导出加密备份、导出明文 JSON、导入加密备份和导入明文 JSON。备份中心独立管理服务器上的手动备份和自动备份，明文导入支持 `skip`、`overwrite`、`ask` 三种冲突策略。

条目列表提供搜索、标签筛选、星标筛选、排序字段和排序方向控制。标签默认按覆盖条目数量降序展示，数量相同时按名称排序；“更多标签”弹窗提供条目数量升/降序和名称升/降序切换，名称排序使用浏览器中文排序规则。回收站弹窗使用后端分页，避免超过第一页的删除项无法访问。

### 3.1 V1.1 产品化交互

首次引导：初始化主密码成功后展示欢迎弹窗，说明主密码不可找回、数据保存在本地加密文件、建议定期备份、支持自动锁定。弹窗提供“导入示例数据”和“跳过”。

示例数据：前端本地生成 3 条明显的假示例条目，标签包含 `示例`，备注包含“这是示例数据，可删除”。示例数据通过现有 `POST /entries` 创建，不新增专用后端接口。

AI 智能录入：打开 AI 弹窗时调用 `GET /ai/status`。未配置时显示“AI 未配置，可继续手动录入”，并提供“转为手动录入”把粘贴内容带入新建条目的备注；即使没有粘贴内容，也允许直接转入空白新建条目。AI 解析失败时也必须保留原文并降级到手动录入。点击“智能解析”后先显示正在解析状态，拿到解析结果后再进入冷却倒计时。AI 返回多条 `parsed_entries` 时，前端展示多条结果，并支持一次性创建多条新条目；单条结果继续进入新建条目表单供用户确认。

AI 输出鲁棒性：后端 prompt 必须要求模型严格返回顶层 `entries` 数组，并启用 JSON object 输出约束。后端需要对常见格式偏差做归一化，包括字段对象/数组、标签字符串、`copyable` 字符串和外层 `items/accounts/records/data` 等别名。

导入冲突：明文导入选择 `ask` 且后端返回 `CONFLICT` 时，显示冲突详情弹窗。弹窗展示冲突数量、前若干条导入标题，并提示可选择跳过、覆盖或取消后重新导入。

标签合并：标签管理弹窗提供“合并标签”区域，用户选择或输入源标签、输入目标标签后调用 `/tags/merge`，成功后刷新标签和条目列表。

移动端验收：重点检查底部批量操作栏可换行、设置页备份按钮不溢出、回收站分页按钮可换行、标签管理按钮布局可触达。

### 3.1.1 V1.2 日常管理增强

条目模板：创建条目时提供模板选择，模板由前端本地定义，不新增后端接口。首批模板包括网站账号、服务器、API Key、安全笔记、银行卡/证件。

DeepSeek AI：AI 成功路径使用 `DEEPSEEK_API_KEY`、`https://api.deepseek.com/chat/completions`、`deepseek-v4-flash`。未配置或失败时继续降级到手动录入。

备份管理 UI：独立备份中心在桌面端以两列展示手动备份和自动备份，移动端上下排列。两列各自拥有独立分页，每页 3 条；即使不足 3 条也保留占位槽并始终显示分页条，避免布局高度跳动。列表项展示文件大小、更新时间、条目数和回收站数，并提供指定备份下载和恢复按钮。操作按钮放在浅色圆角操作框中，并按动作使用低饱和浅色区分：加密下载偏蓝、明文 JSON 偏琥珀、恢复偏绿。恢复前必须进入三步向导，核对页展示当前 vault 与备份目标状态的条目/回收站数量对比，并输入 `RESTORE`。

导入预览：选择明文 JSON 后先调用预览接口，显示总条目、新增条目、冲突条目和冲突样例，用户确认后再导入。

搜索范围选择：搜索框下方必须提供可点击的范围框，包括标题、网址、标签、字段名、非可复制字段值、备注。默认全部不选中；用户点击某个范围后，搜索才会在该范围内匹配；全部未选时，输入搜索词不返回结果。

搜索边界：列表搜索不得匹配可复制字段的明文值，避免密码、API Key、token 等隐藏内容造成“看似无关”的结果命中。搜索可以匹配标题、网址、标签、字段名、非可复制字段值和备注。

高级筛选：支持多标签、无标签、创建时间范围、更新时间范围。多标签输入必须支持 chip 形式，回车、Tab、英文逗号、中文逗号均可确认标签，同时支持粘贴中英文逗号分隔文本。时间范围必须明确标注“创建时间”和“更新时间”，并显示默认范围 `1970-01-01` 至 `9999-12-31`（等同全部）；筛选输入留空表示不限。筛选条件变化后回到第一页。

主题表单控件：输入框、下拉框、文本域、日期选择器、按钮和选项必须继承当前主题的文字色与背景色。暗色主题和系统暗色模式必须设置 `color-scheme: dark`，避免浏览器原生控件文字融入背景。

高级筛选标签 chip：chip 必须使用独立的蓝色实心背景和白色文字，不依赖通用 `.tag` 样式，确保亮色和暗色主题下都清晰可见。

密码健康检查：工具区展示弱密码、重复密码、长期未更新条目，只在已解锁数据中本地计算。

字段显隐：详情页可复制字段默认隐藏，点击显示后再展示明文；复制不要求先显示。

复制反馈：复制成功后显示明确反馈；剪贴板自动清理可作为可选增强。

数据维护工具：工具区展示重复标题、无标签条目、空字段条目、示例数据条目，并提供可跳转筛选或批量删除示例数据的入口。

AI 防滥用：智能解析按钮在解析成功拿到结果后进入 5 秒冷却；输入内容未变化时不能重复解析。后端同时返回 429 兜底，防止绕过前端频繁调用。

### 3.1.2 V1.3 体验增强

AI 多条录入增强：AI 返回多条解析结果后，前端必须允许逐条勾选、编辑标题、网址、标签、备注和字段，再应用创建。未勾选的解析结果不得创建。

导入预览勾选：明文 JSON 导入预览必须展示条目列表、冲突状态、字段数和标签数。用户可以全选、清空选择或逐条勾选，确认导入时只导入已选择条目。

高级筛选增强：当前筛选条件必须以 chip 形式展示在筛选按钮下方，并支持单个条件快速移除。高级筛选新增有网址/无网址、有备注/无备注。常用筛选保存在浏览器本地 `localStorage`，不进入加密 vault。

维护工具可操作化：健康检查和维护报告中的统计项必须可点击定位到对应条目。无标签条目必须支持从维护工具批量添加标签。弱密码、重复密码和空字段只做定位，不自动修改敏感内容。

导入冲突逐条处理：导入预览中的冲突条目必须支持逐条选择跳过、覆盖或停止。确认导入时只处理已勾选条目，并按逐条策略优先于全局冲突策略执行。

备份体验增强：备份中心必须提供手动创建备份入口。手动备份不会被自动备份轮转删除；自动备份用于写入前回滚并按设置中的 `auto_backup_retention` 清理，默认 30、范围 5-200。恢复备份前必须读取并展示备份概况，包括条目数、回收站条目数、文件大小和修改时间，并明确提示恢复会替换当前 vault。

### 3.1.3 V1.4 小体验增强

列表状态提示：当搜索、标签、星标、高级筛选、维护工具定位或非默认排序生效时，列表顶部必须展示当前状态提示。用户必须能一键清除定位、搜索、筛选、排序和选择状态，避免误以为数据丢失。

导入完成报告：明文导入成功后必须展示导入完成报告，包括本次选择、成功导入、新增、覆盖、跳过和冲突数量。后端导入响应增加 `created_count` 和 `overwritten_count`，旧字段 `imported_count`、`skipped_count`、`conflicts` 保持兼容。

AI 失败原因提示：AI 解析失败时必须区分冷却、未解锁、AI 服务/API 不可用、请求无效等情况，保留原文并提供转为手动录入入口。不得阻塞手动录入。

备份体验小修：手动备份创建、刷新列表、下载备份和恢复执行期间显示 loading，成功后自动刷新备份列表并高亮新备份。备份中心必须说明手动备份不自动清理、自动备份会按保留数量轮转。恢复向导读取概况时必须显示正在读取提示，并在确认步骤强调会替换当前 vault。

批量操作体验小修：底部批量操作栏必须显示已选条目数量，提供当前页全选/取消全选入口。批量删除、批量加标签、批量移除标签前必须显示明确确认文案。

视觉重构约束：V1.4 可以全面优化页面视觉设计，包括主题变量、卡片层级、粘性 header/footer、状态条、模态框和移动端布局；不得改变现有功能入口、接口路径、数据结构语义或 V1.3 已验收行为。

V1.4 回归修复：自动锁定到期后前端必须立即清理本地解锁态并回到解锁页；收到后端 `401` 且提示需要解锁时，也必须同步切回解锁页。标签下拉菜单必须支持点击外部区域关闭。

### 3.2 应用入口

```javascript
// app.js
const { createApp, ref, reactive, computed, watch, onMounted } = Vue;

const app = createApp({
  setup() {
    // 全局状态
    const state = reactive({
      locked: true,
      initialized: false,
      currentPage: 'home',
      entries: [],
      tags: [],
      trash: [],
      settings: {},
      pagination: {
        page: 1,
        pageSize: 20,
        total: 0
      }
    });

    // 页面切换
    const currentPage = computed(() => state.currentPage);
    
    // 初始化
    onMounted(async () => {
      await checkAuthStatus();
      if (!state.locked) {
        await loadData();
      }
    });

    return {
      state,
      currentPage,
      // ... 其他方法和属性
    };
  }
});

app.mount('#app');
```

### 3.3 状态管理

```javascript
// store.js
class Store {
  constructor() {
    this.state = reactive({
      locked: true,
      initialized: false,
      entries: [],
      tags: [],
      trash: [],
      settings: {
        theme: 'system',
        pageSize: 20,
        autoLockMinutes: 5
      },
      pagination: {
        page: 1,
        pageSize: 20,
        total: 0
      },
      filters: {
        search: '',
        tag: null,
        starred: false,
        sortBy: 'updated_at',
        sortOrder: 'desc'
      }
    });
  }

  // 获取条目列表
  async fetchEntries() {
    const params = new URLSearchParams({
      page: this.state.pagination.page,
      page_size: this.state.pagination.pageSize,
      search: this.state.filters.search,
      sort_by: this.state.filters.sortBy,
      sort_order: this.state.filters.sortOrder
    });
    
    if (this.state.filters.tag) {
      params.append('tag', this.state.filters.tag);
    }
    if (this.state.filters.starred) {
      params.append('starred', 'true');
    }
    
    const response = await api.get(`/entries?${params}`);
    this.state.entries = response.data.items;
    this.state.pagination.total = response.data.pagination.total;
  }

  // 创建条目
  async createEntry(entry) {
    const response = await api.post('/entries', entry);
    await this.fetchEntries();
    return response;
  }

  // 更新条目
  async updateEntry(id, updates) {
    const response = await api.put(`/entries/${id}`, updates);
    await this.fetchEntries();
    return response;
  }

  // 删除条目
  async deleteEntry(id) {
    const response = await api.delete(`/entries/${id}`);
    await this.fetchEntries();
    return response;
  }

  // ... 其他方法
}

const store = new Store();
```

## 4. 组件设计

本章描述的是前端交互单元和 V2 组件化目标。V1 可以把这些交互直接实现在 `index.html` 和 `js/app.js` 中，但行为必须与本章一致。

### 4.1 条目卡片组件

```javascript
// components/EntryCard.js
const EntryCard = {
  props: {
    entry: Object,
    selectable: Boolean,
    selected: Boolean
  },
  emits: ['select', 'edit', 'delete', 'copy'],
  template: `
    <div class="entry-card" :class="{ selected }">
      <div class="card-header">
        <input 
          v-if="selectable" 
          type="checkbox" 
          :checked="selected"
          @change="$emit('select', entry.id)"
        />
        <img :src="faviconUrl" class="favicon" />
        <h3 class="title">{{ entry.title }}</h3>
        <button 
          class="star-btn" 
          :class="{ starred: entry.starred }"
          @click="toggleStar"
        >
          {{ entry.starred ? '★' : '☆' }}
        </button>
      </div>
      
      <div class="card-tags">
        <span 
          v-for="tag in entry.tags" 
          :key="tag"
          class="tag"
          :style="{ backgroundColor: getTagColor(tag) }"
          @click="$emit('filter-tag', tag)"
        >
          {{ tag }}
        </span>
      </div>
      
      <div class="card-fields">
        <div 
          v-for="field in entry.fields" 
          :key="field.name"
          class="field"
        >
          <span class="field-name">{{ field.name }}</span>
          <span class="field-value" :class="{ masked: !field.revealed }">
            {{ field.revealed ? field.value : '••••••' }}
          </span>
          <button 
            v-if="field.copyable" 
            class="copy-btn"
            @click="copyField(field)"
          >
            复制
          </button>
        </div>
      </div>
      
      <div class="card-actions">
        <button class="action-btn" @click="$emit('edit', entry)">编辑</button>
        <button class="action-btn" @click="openUrl" v-if="entry.url">打开</button>
        <button class="action-btn copy-all" @click="showCopyMenu">复制</button>
      </div>
    </div>
  `,
  setup(props, { emit }) {
    const faviconUrl = computed(() => {
      if (props.entry.url) {
        try {
          const domain = new URL(props.entry.url).hostname;
          return `https://favicon.im/${domain}`;
        } catch {
          return '';
        }
      }
       return '';
    });

    const getTagColor = (tag) => {
      return store.getTagColor(tag);
    };

    const toggleStar = () => {
      emit('edit', { ...props.entry, starred: !props.entry.starred });
    };

    const copyField = async (field) => {
      try {
        await navigator.clipboard.writeText(field.value);
        showToast('已复制到剪贴板');
        emit('copy', field);
      } catch (err) {
        showToast('复制失败', 'error');
      }
    };

    const openUrl = () => {
      window.open(props.entry.url, '_blank');
    };

    return {
      faviconUrl,
      getTagColor,
      toggleStar,
      copyField,
      openUrl
    };
  }
};
```

### 4.2 分页组件

```javascript
// components/Pagination.js
const Pagination = {
  props: {
    currentPage: Number,
    totalPages: Number,
    totalItems: Number,
    pageSize: Number
  },
  emits: ['page-change', 'page-size-change'],
  template: `
    <div class="pagination">
      <div class="pagination-info">
        共 {{ totalItems }} 条，每页
        <select :value="pageSize" @change="onPageSizeChange">
          <option value="10">10</option>
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
        条
      </div>
      
      <div class="pagination-controls">
        <button 
          class="page-btn" 
          :disabled="currentPage === 1"
          @click="$emit('page-change', 1)"
        >
          首页
        </button>
        <button 
          class="page-btn" 
          :disabled="currentPage === 1"
          @click="$emit('page-change', currentPage - 1)"
        >
          上一页
        </button>
        
        <template v-for="page in visiblePages" :key="page">
          <button 
            v-if="page === '...'"
            class="page-btn ellipsis"
            disabled
          >
            ...
          </button>
          <button 
            v-else
            class="page-btn" 
            :class="{ active: page === currentPage }"
            @click="$emit('page-change', page)"
          >
            {{ page }}
          </button>
        </template>
        
        <button 
          class="page-btn" 
          :disabled="currentPage === totalPages"
          @click="$emit('page-change', currentPage + 1)"
        >
          下一页
        </button>
        <button 
          class="page-btn" 
          :disabled="currentPage === totalPages"
          @click="$emit('page-change', totalPages)"
        >
          末页
        </button>
      </div>
    </div>
  `,
  setup(props) {
    const visiblePages = computed(() => {
      const pages = [];
      const total = props.totalPages;
      const current = props.currentPage;
      
      if (total <= 7) {
        for (let i = 1; i <= total; i++) pages.push(i);
      } else {
        pages.push(1);
        if (current > 3) pages.push('...');
        for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
          pages.push(i);
        }
        if (current < total - 2) pages.push('...');
        pages.push(total);
      }
      
      return pages;
    });

    const onPageSizeChange = (e) => {
      emit('page-size-change', parseInt(e.target.value));
    };

    return { visiblePages, onPageSizeChange };
  }
};
```

### 4.3 搜索栏组件

```javascript
// components/SearchBar.js
const SearchBar = {
  props: {
    modelValue: String
  },
  emits: ['update:modelValue', 'search'],
  template: `
    <div class="search-bar">
      <input 
        type="text"
        :value="modelValue"
        @input="onInput"
        placeholder="搜索条目..."
        class="search-input"
      />
      <button v-if="modelValue" class="clear-btn" @click="clear">✕</button>
    </div>
  `,
  setup(props, { emit }) {
    let debounceTimer = null;

    const onInput = (e) => {
      const value = e.target.value;
      emit('update:modelValue', value);
      
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        emit('search', value);
      }, 300);
    };

    const clear = () => {
      emit('update:modelValue', '');
      emit('search', '');
    };

    return { onInput, clear };
  }
};
```

## 5. 主题系统

### 5.1 CSS 变量定义

```css
/* css/themes/variables.css */
:root {
  /* 颜色 */
  --color-primary: #4a90d9;
  --color-primary-hover: #3a7bc8;
  --color-primary-light: rgba(74, 144, 217, 0.1);
  
  --color-success: #52c41a;
  --color-warning: #faad14;
  --color-error: #ff4d4f;
  --color-info: #1890ff;
  
  /* 背景 */
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-card: #ffffff;
  --bg-modal: rgba(0, 0, 0, 0.5);
  
  /* 文本 */
  --text-primary: #333333;
  --text-secondary: #666666;
  --text-tertiary: #999999;
  --text-inverse: #ffffff;
  
  /* 边框 */
  --border-color: #e0e0e0;
  --border-radius: 8px;
  --border-radius-lg: 12px;
  
  /* 阴影 */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
  
  /* 间距 */
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  
  /* 字体 */
  --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-size-xs: 12px;
  --font-size-sm: 14px;
  --font-size-md: 16px;
  --font-size-lg: 18px;
  --font-size-xl: 20px;
  
  /* 动画 */
  --transition-fast: 0.1s ease;
  --transition-normal: 0.2s ease;
  --transition-slow: 0.3s ease;
}
```

### 5.2 暗色主题

```css
/* css/themes/dark.css */
[data-theme="dark"] {
  --color-primary: #5a9fe6;
  --color-primary-hover: #6ab0f0;
  --color-primary-light: rgba(90, 159, 230, 0.15);
  
  --bg-primary: #1a1a1a;
  --bg-secondary: #2d2d2d;
  --bg-card: #333333;
  --bg-modal: rgba(0, 0, 0, 0.7);
  
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
  --text-tertiary: #999999;
  --text-inverse: #333333;
  
  --border-color: #444444;
  
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.3);
}
```

### 5.3 亮色主题

```css
/* css/themes/light.css */
[data-theme="light"] {
  /* 使用 variables.css 中的默认值 */
}
```

### 5.4 系统主题

```css
/* css/themes/system.css */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    --color-primary: #5a9fe6;
    --color-primary-hover: #6ab0f0;
    --color-primary-light: rgba(90, 159, 230, 0.15);
    
    --bg-primary: #1a1a1a;
    --bg-secondary: #2d2d2d;
    --bg-card: #333333;
    --bg-modal: rgba(0, 0, 0, 0.7);
    
    --text-primary: #ffffff;
    --text-secondary: #cccccc;
    --text-tertiary: #999999;
    --text-inverse: #333333;
    
    --border-color: #444444;
    
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
    --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.3);
  }
}
```

### 5.5 主题切换逻辑

```javascript
// js/theme.js
class ThemeManager {
  constructor() {
    this.currentTheme = 'system';
    this.mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  }

  async init() {
    // 从后端获取设置
    const settings = await api.get('/settings');
    this.currentTheme = settings.data.theme || 'system';
    this.apply();
    
    // 监听系统主题变化
    this.mediaQuery.addEventListener('change', () => {
      if (this.currentTheme === 'system') {
        this.apply();
      }
    });
  }

  async setTheme(theme) {
    this.currentTheme = theme;
    this.apply();
    
    // 保存到后端
    await api.put('/settings', { theme });
  }

  apply() {
    const root = document.documentElement;
    
    if (this.currentTheme === 'system') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', this.currentTheme);
    }
  }

  getEffectiveTheme() {
    if (this.currentTheme === 'system') {
      return this.mediaQuery.matches ? 'dark' : 'light';
    }
    return this.currentTheme;
  }
}

const themeManager = new ThemeManager();
```

## 6. 移动端适配

V1.1 手动验收清单：

- 375px 宽度下底部批量操作栏按钮和输入框不横向溢出。
- 375px 宽度下设置页备份按钮换行显示，文件选择控件仍可点击。
- 375px 宽度下回收站分页、清空按钮换行显示。
- 375px 宽度下标签管理条目、重命名、删除、合并操作不遮挡。
- 768px 左右平板宽度下条目卡片、弹窗和分页保持可读。

### 6.1 响应式断点

```css
/* css/responsive.css */
/* 移动端 */
@media (max-width: 767px) {
  .desktop-only {
    display: none !important;
  }
  
  .entry-list {
    grid-template-columns: 1fr;
  }
  
  .header {
    padding: 0 12px;
  }
  
  .bottom-nav {
    display: flex;
  }
  
  .sidebar {
    display: none;
  }
  
  .main-content {
    padding-bottom: 60px; /* 为底部导航留空间 */
  }
}

/* 平板 */
@media (min-width: 768px) and (max-width: 1023px) {
  .mobile-only {
    display: none !important;
  }
  
  .entry-list {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 桌面 */
@media (min-width: 1024px) {
  .mobile-only {
    display: none !important;
  }
  
  .entry-list {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}
```

### 6.2 底部导航栏

```javascript
// components/BottomNav.js
const BottomNav = {
  props: {
    currentPage: String
  },
  emits: ['navigate'],
  template: `
    <nav class="bottom-nav mobile-only">
      <button 
        v-for="item in navItems" 
        :key="item.id"
        class="nav-item"
        :class="{ active: currentPage === item.id }"
        @click="$emit('navigate', item.id)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>
  `,
  setup() {
    const navItems = [
      { id: 'home', icon: '🏠', label: '主页' },
      { id: 'tags', icon: '🏷️', label: '标签' },
      { id: 'trash', icon: '🗑️', label: '回收站' },
      { id: 'settings', icon: '⚙️', label: '设置' }
    ];

    return { navItems };
  }
};
```

```css
/* css/components/bottom-nav.css */
.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  display: none;
  justify-content: space-around;
  align-items: center;
  z-index: 100;
}

.bottom-nav .nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.bottom-nav .nav-item.active {
  color: var(--color-primary);
}

.bottom-nav .nav-icon {
  font-size: 24px;
  margin-bottom: 4px;
}
```

### 6.3 触摸优化

```css
/* 触摸友好的按钮大小 */
button, .btn, .action-btn {
  min-height: 44px;
  min-width: 44px;
}

/* 卡片点击区域 */
.entry-card {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

/* 长按菜单 */
.entry-card:active {
  transform: scale(0.98);
}

/* 输入框大小 */
input, select, textarea {
  font-size: 16px; /* 防止 iOS 缩放 */
  padding: 12px;
}
```

## 7. API 封装

### 7.1 API 客户端

```javascript
// js/api.js
class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
    this.token = null;
  }

  setToken(token) {
    this.token = token;
  }

  async request(method, path, data = null) {
    const headers = {
      'Content-Type': 'application/json'
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const options = {
      method,
      headers
    };

    if (data && method !== 'GET') {
      options.body = JSON.stringify(data);
    }

    const response = await fetch(`${this.baseUrl}${path}`, options);
    const result = await response.json();

    if (!response.ok) {
      throw new ApiError(result.error, result.message, response.status);
    }

    return result;
  }

  get(path) {
    return this.request('GET', path);
  }

  post(path, data) {
    return this.request('POST', path, data);
  }

  put(path, data) {
    return this.request('PUT', path, data);
  }

  delete(path) {
    return this.request('DELETE', path);
  }

  async upload(path, file, additionalData = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    for (const [key, value] of Object.entries(additionalData)) {
      formData.append(key, value);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Authorization': this.token ? `Bearer ${this.token}` : ''
      },
      body: formData
    });

    return response.json();
  }
}

class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

const api = new ApiClient();
```

## 8. 工具函数

### 8.1 标签颜色生成

```javascript
// js/utils.js
function djb2Hash(str) {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash) + str.charCodeAt(i);
    hash = hash & hash;
  }
  return Math.abs(hash);
}

function getTagColor(tagName) {
  const hash = djb2Hash(tagName);
  const hue = hash % 360;
  return `hsl(${hue}, 65%, 55%)`;
}
```

### 8.2 日期格式化

```javascript
function formatDate(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;
  
  // 1 分钟内
  if (diff < 60000) {
    return '刚刚';
  }
  
  // 1 小时内
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)} 分钟前`;
  }
  
  // 24 小时内
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)} 小时前`;
  }
  
  // 7 天内
  if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)} 天前`;
  }
  
  // 超过 7 天
  return date.toLocaleDateString('zh-CN');
}
```

### 8.3 防抖函数

```javascript
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
```

## 9. 错误处理

### 9.1 全局错误处理

```javascript
// js/error-handler.js
function setupErrorHandler(app) {
  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue error:', err, info);
    
    if (err instanceof ApiError) {
      switch (err.code) {
        case 'UNAUTHORIZED':
          store.lock();
          showToast('会话已过期，请重新解锁', 'warning');
          break;
        case 'CONFLICT':
          showToast('数据已被修改，请刷新页面', 'error');
          break;
        default:
          showToast(err.message, 'error');
      }
    } else {
      showToast('发生未知错误', 'error');
    }
  };
}
```

### 9.2 Toast 提示组件

```javascript
// components/Toast.js
const Toast = {
  props: {
    message: String,
    type: String, // success, error, warning, info
    duration: {
      type: Number,
      default: 3000
    }
  },
  template: `
    <div class="toast" :class="type" v-if="visible">
      <span class="toast-icon">{{ icon }}</span>
      <span class="toast-message">{{ message }}</span>
    </div>
  `,
  setup(props) {
    const visible = ref(true);
    
    const icon = computed(() => {
      switch (props.type) {
        case 'success': return '✓';
        case 'error': return '✕';
        case 'warning': return '⚠';
        default: return 'ℹ';
      }
    });

    onMounted(() => {
      setTimeout(() => {
        visible.value = false;
      }, props.duration);
    });

    return { visible, icon };
  }
};

// Toast 管理器
const toastContainer = document.createElement('div');
toastContainer.id = 'toast-container';
document.body.appendChild(toastContainer);

function showToast(message, type = 'info', duration = 3000) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${getIcon(type)}</span>
    <span class="toast-message">${message}</span>
  `;
  
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
```

## 10. 性能优化

性能优化分阶段执行。V1 通过分页控制单页渲染数量；V2 在条目数量明显增长后再引入虚拟滚动，避免过早复杂化。

### 10.1 虚拟滚动（大量条目时）

阶段：V2。V1 不要求虚拟滚动，分页是默认性能策略。

```javascript
// components/VirtualList.js
const VirtualList = {
  props: {
    items: Array,
    itemHeight: Number,
    bufferSize: {
      type: Number,
      default: 5
    }
  },
  template: `
    <div class="virtual-list" @scroll="onScroll" ref="container">
      <div class="virtual-list-spacer" :style="{ height: totalHeight + 'px' }">
        <div 
          v-for="item in visibleItems" 
          :key="item.id"
          class="virtual-list-item"
          :style="{ transform: 'translateY(' + item.top + 'px)' }"
        >
          <slot :item="item.data"></slot>
        </div>
      </div>
    </div>
  `,
  setup(props) {
    const container = ref(null);
    const scrollTop = ref(0);

    const totalHeight = computed(() => props.items.length * props.itemHeight);

    const visibleItems = computed(() => {
      const startIndex = Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.bufferSize);
      const endIndex = Math.min(
        props.items.length,
        Math.ceil((scrollTop.value + container.value?.clientHeight || 0) / props.itemHeight) + props.bufferSize
      );

      return props.items.slice(startIndex, endIndex).map((item, index) => ({
        data: item,
        top: (startIndex + index) * props.itemHeight
      }));
    });

    const onScroll = (e) => {
      scrollTop.value = e.target.scrollTop;
    };

    return { container, totalHeight, visibleItems, onScroll };
  }
};
```

### 10.2 图片懒加载

```javascript
// 懒加载 favicon
const LazyFavicon = {
  props: {
    url: String
  },
  template: `
    <img 
      v-if="loaded"
      :src="src"
      class="favicon"
      @error="onError"
    />
    <div v-else class="favicon-placeholder"></div>
  `,
  setup(props) {
    const loaded = ref(false);
    const src = ref('');

    const load = () => {
      if (props.url) {
        try {
          const domain = new URL(props.url).hostname;
          src.value = `https://favicon.im/${domain}`;
          loaded.value = true;
        } catch {
          src.value = '';
          loaded.value = true;
        }
      }
    };

    const onError = () => {
      src.value = '';
    };

    onMounted(load);

    return { loaded, src, onError };
  }
};
```
