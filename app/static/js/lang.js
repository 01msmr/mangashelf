/**
 * Lightweight frontend i18n module.
 * Loads /static/lang.json once; provides t(key) for translations.
 * Language is stored in localStorage so it persists without a server call.
 */
const Lang = (() => {
    let _strings = null;
    let _current = localStorage.getItem('mangashelf_lang') || 'de';

    return {
        get current() { return _current; },

        /** Fetch and cache lang.json. Call once at page init. */
        async load() {
            if (_strings) return;
            const resp = await fetch('/static/lang.json');
            _strings = await resp.json();
        },

        /** Translate key with optional {{var}} substitution; falls back to English, then the raw key. */
        t(key, vars = {}) {
            if (!_strings) return key;
            let str = (_strings[_current] && _strings[_current][key] !== undefined)
                ? _strings[_current][key]
                : (_strings['en'] && _strings['en'][key] !== undefined)
                    ? _strings['en'][key]
                    : key;
            return str.replace(/\{\{(\w+)\}\}/g, (_, k) => vars[k] !== undefined ? vars[k] : `{{${k}}}`);
        },

        /** Persist language selection to localStorage. */
        set(lang) {
            _current = lang;
            localStorage.setItem('mangashelf_lang', lang);
        },
    };
})();
