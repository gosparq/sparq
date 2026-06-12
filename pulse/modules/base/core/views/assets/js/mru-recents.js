// Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
// MRU (Most Recently Used) sidebar recents
// Tracks up to 5 recently visited projects, action items, and people profiles.
// Storage: localStorage key 'sparq-mru-recents' — array of {type, id, name, url}
window.SparqMRU = {
    KEY: 'sparq-mru-recents',
    MAX: 5,

    read: function () {
        try {
            return JSON.parse(localStorage.getItem(this.KEY) || '[]');
        } catch (e) {
            return [];
        }
    },

    add: function (type, id, name, url, rawTitle) {
        var items = this.read().filter(function (item) { return item.url !== url; });
        items.unshift({ type: type, id: id, name: name, url: url, rawTitle: rawTitle || name });
        localStorage.setItem(this.KEY, JSON.stringify(items.slice(0, this.MAX)));
    }
};
