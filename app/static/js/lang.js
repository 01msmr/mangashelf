/**
 * Lightweight frontend i18n module.
 * Loads /static/lang.json once; provides t(key) for translations.
 * Language is stored in localStorage so it persists without a server call.
 */
const Lang = (() => {
    let _strings = null;
    let _current = localStorage.getItem('mangastore_lang') || 'de';

    return {
        get current() { return _current; },

        /** Fetch and cache lang.json. Call once at page init. */
        async load() {
            if (_strings) return;
            const resp = await fetch('/static/lang.json');
            _strings = await resp.json();
        },

        /** Translate key; falls back to English, then the raw key. */
        t(key) {
            if (!_strings) return key;
            return (_strings[_current] && _strings[_current][key] !== undefined)
                ? _strings[_current][key]
                : (_strings['en'] && _strings['en'][key] !== undefined)
                    ? _strings['en'][key]
                    : key;
        },

        /** Persist language selection to localStorage. */
        set(lang) {
            _current = lang;
            localStorage.setItem('mangastore_lang', lang);
        },
    };
})();
