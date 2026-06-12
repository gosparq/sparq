// Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

window.ghTriggerInit = function (elementOrId, objectType, objectId, externalRepo) {
    var el = (typeof elementOrId === 'string') ? document.getElementById(elementOrId) : elementOrId;
    if (!el) return;

    var dropdown = null;
    var debounce = null;
    var triggerStart = -1;
    var activeIdx = -1;

    function detectTrigger() {
        var text = el.value.substring(0, el.selectionStart);
        var match = text.match(/(^|[\s\n])(#(\w*))$/);
        if (match) { triggerStart = el.selectionStart - match[2].length; return match[3]; }
        triggerStart = -1;
        return null;
    }

    function replaceQuery(issueNum) {
        if (triggerStart < 0) return;
        var before = el.value.substring(0, triggerStart);
        var after  = el.value.substring(el.selectionStart);
        var token  = '[GH-' + issueNum + ']';
        el.value = before + token + after;
        var newPos = triggerStart + token.length;
        el.setSelectionRange(newPos, newPos);
        el.dispatchEvent(new Event('input'));
        triggerStart = -1;
    }

    function dismissDropdown() {
        if (dropdown) { dropdown.remove(); dropdown = null; activeIdx = -1; }
    }

    function renderDropdown(issues) {
        dismissDropdown();
        if (!issues || !issues.length) return;
        dropdown = document.createElement('div');
        dropdown.className = 'gh-issue-dropdown';
        var rect = el.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top  = (rect.bottom + 2) + 'px';
        dropdown.style.left = rect.left + 'px';
        dropdown.style.width = Math.max(rect.width, 280) + 'px';
        issues.forEach(function (issue) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'gh-issue-dropdown__item';
            var numSpan = document.createElement('span');
            numSpan.className = 'gh-issue-dropdown__num';
            numSpan.textContent = '#' + issue.number;
            btn.appendChild(numSpan);
            btn.appendChild(document.createTextNode(issue.title));
            btn.addEventListener('mousedown', function (e) { e.preventDefault(); selectIssue(issue); });
            dropdown.appendChild(btn);
        });
        document.body.appendChild(dropdown);
        activeIdx = -1;
    }

    function updateActiveItem() {
        if (!dropdown) return;
        dropdown.querySelectorAll('.gh-issue-dropdown__item').forEach(function (item, i) {
            item.classList.toggle('gh-active', i === activeIdx);
        });
    }

    function selectIssue(issue) {
        replaceQuery(issue.number);
        dismissDropdown();
        fetch('/integrations/github/refs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ external_id: issue.number, external_repo: externalRepo, object_type: objectType, object_id: objectId }),
        }).catch(function () {});
    }

    function fetchIssues(query) {
        fetch('/integrations/github/issues?q=' + encodeURIComponent(query))
            .then(function (r) { return r.ok ? r.json() : { connected: false }; })
            .then(function (data) { if (data.connected) renderDropdown(data.issues || []); })
            .catch(function () {});
    }

    el.addEventListener('input', function () {
        var query = detectTrigger();
        clearTimeout(debounce);
        if (query === null) { dismissDropdown(); return; }
        debounce = setTimeout(function () { fetchIssues(query); }, 200);
    });

    el.addEventListener('keydown', function (e) {
        if (!dropdown) return;
        var items = dropdown.querySelectorAll('.gh-issue-dropdown__item');
        if (e.key === 'ArrowDown') { e.preventDefault(); activeIdx = Math.min(activeIdx + 1, items.length - 1); updateActiveItem(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); activeIdx = Math.max(activeIdx - 1, 0); updateActiveItem(); }
        else if (e.key === 'Enter' && activeIdx >= 0) { e.preventDefault(); items[activeIdx].dispatchEvent(new MouseEvent('mousedown')); }
        else if (e.key === 'Escape') { dismissDropdown(); }
    });

    el.addEventListener('blur', function () { setTimeout(dismissDropdown, 150); });
};

if (!window._ghChipReady) { window._ghChipReady = true; (function () {
    var _popover = null;   // current popover node (lives in <body> while visible)
    var _chip = null;      // chip it belongs to
    var _hideTimer = null;

    function _position(popover, chip) {
        var rect = chip.getBoundingClientRect();
        var left = rect.left;
        if (left + 320 > window.innerWidth - 8) { left = window.innerWidth - 320 - 8; }
        popover.style.position = 'fixed';
        popover.style.top  = (rect.bottom + 4) + 'px';
        popover.style.left = left + 'px';
    }

    function _doHide() {
        if (!_popover) return;
        _popover.style.display = 'none';
        if (_chip) { _chip.appendChild(_popover); }
        _popover = null;
        _chip = null;
    }

    function showPopover(chip) {
        clearTimeout(_hideTimer);
        if (_chip === chip) return;            // already showing for this chip
        _doHide();                             // close any other open popover

        var popover = chip.querySelector('.gh-popover');
        if (!popover) return;

        document.body.appendChild(popover);   // escape chip's stacking context
        _popover = popover;
        _chip = chip;

        _position(popover, chip);
        popover.style.display = 'block';
    }

    function scheduleHide(chip) {
        if (_chip !== chip) return;
        _hideTimer = setTimeout(_doHide, 80);
    }

    // Keep popover alive while mouse is over it
    document.addEventListener('mouseover', function (e) {
        if (_popover && (e.target === _popover || _popover.contains(e.target))) {
            clearTimeout(_hideTimer);
            return;
        }
        var chip = e.target.closest('.gh-chip');
        if (chip) { showPopover(chip); }
    });

    document.addEventListener('mouseout', function (e) {
        // Moving within the popover — ignore
        if (_popover && (e.target === _popover || _popover.contains(e.target))) {
            if (e.relatedTarget && (_popover === e.relatedTarget || _popover.contains(e.relatedTarget))) return;
            scheduleHide(_chip);
            return;
        }
        var chip = e.target.closest('.gh-chip');
        if (!chip) return;
        // Moving to popover — don't hide
        if (e.relatedTarget && _popover && (_popover === e.relatedTarget || _popover.contains(e.relatedTarget))) return;
        // Moving within chip subtree — ignore
        if (e.relatedTarget && chip.contains(e.relatedTarget)) return;
        scheduleHide(chip);
    });
})(); }
