/**
 * 全局 Store 装配。
 *
 * 状态形状和各 API 领域方法分散在独立模块中，这里保留稳定的 store 调用面。
 */
class Store {
    constructor() {
        this.state = window.SecretBaseStoreState.createInitialStoreState();
        this.listeners = [];
    }

    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(item => item !== listener);
        };
    }

    notify() {
        this.listeners.forEach(listener => listener(this.state));
    }

    setState(updates) {
        Object.assign(this.state, updates);
        this.notify();
    }

    setFilter(key, value) {
        this.state.filters[key] = value;
        this.notify();
    }

    clearFilters() {
        this.state.filters = window.SecretBaseStoreState.createDefaultFilters();
        this.notify();
    }
}

Object.assign(
    Store.prototype,
    window.SecretBaseStoreAuthSettings.createAuthAndSettingsMethods({
        api,
        normalizeSettings: window.SecretBaseStoreState.normalizeSettings,
        toBackendSettings: window.SecretBaseStoreState.toBackendSettings
    }),
    window.SecretBaseStoreEntryMethods.createEntryMethods({
        api,
        showToast,
        normalizePagination: window.SecretBaseStoreState.normalizePagination,
        buildEntrySearchParams: window.SecretBaseStoreState.buildEntrySearchParams
    }),
    window.SecretBaseStoreTaxonomyMethods.createTaxonomyMethods({ api, showToast }),
    window.SecretBaseStoreTrashMethods.createTrashMethods({ api, showToast })
);

const store = new Store();
