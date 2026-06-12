/**
 * Chat SocketIO Handlers
 *
 * This file contains vanilla JavaScript for real-time chat functionality.
 * It handles WebSocket connections via SocketIO for:
 * - New message notifications
 * - Message updates (pin/unpin)
 * - Message deletions
 * - Channel creation/deletion
 * - User presence updates
 * - Direct message notifications
 * - sparQy agent localStorage management
 *
 * Architecture Note:
 * - Alpine.js handles UI state (inline in templates)
 * - This file handles real-time events (cannot be done in Alpine)
 * - HTMX handles server-driven updates (inline attributes)
 * - sparQy messages use per-user localStorage for persistence (not DB)
 */

(function() {
    'use strict';

    // =========================================================================
    // LocalStorage Keys for sparQy messages (per-user scoped)
    // =========================================================================
    var AGENT_STORAGE_KEY_PREFIX = 'sparq_agent_messages_';

    // =========================================================================
    // Typing Indicator State
    // =========================================================================
    var typingUsers = {};  // { channel: { odIdOrThreadId: { userId: { name, timeout } } } }
    var typingTimeout = null;
    var TYPING_TIMEOUT_MS = 3000;  // Clear typing after 3 seconds of no activity

    // =========================================================================
    // Utility Functions
    // =========================================================================

    /**
     * Reorder mobile channel drawer items: channels with unread badges
     * visible first, then remaining channels alphabetically.
     */
    function reorderMobileChannels() {
        var container = document.querySelector('.channel-sheet-content');
        if (!container) return;

        var items = Array.from(container.querySelectorAll('.channel-sheet-item'));
        if (items.length === 0) return;

        items.sort(function(a, b) {
            // Channels with visible unread badges come first
            var aUnread = a.querySelector('.unread');
            var bUnread = b.querySelector('.unread');
            var aHasUnread = aUnread && aUnread.style.display !== 'none' && parseInt(aUnread.textContent || '0') > 0;
            var bHasUnread = bUnread && bUnread.style.display !== 'none' && parseInt(bUnread.textContent || '0') > 0;

            if (aHasUnread && !bHasUnread) return -1;
            if (!aHasUnread && bHasUnread) return 1;

            // Alphabetical within each group
            var aName = (a.dataset.channel || '').toLowerCase();
            var bName = (b.dataset.channel || '').toLowerCase();
            return aName.localeCompare(bName);
        });

        // Re-append in sorted order (moves elements, no cloning needed)
        items.forEach(function(item) {
            container.appendChild(item);
        });
    }
    window.reorderMobileChannels = reorderMobileChannels;

    /**
     * Scroll chat container to bottom with smooth animation.
     */
    function scrollToBottom() {
        var container = document.querySelector('.chat-messages-container') || document.querySelector('.mobile-messages-container');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    /**
     * Scroll DM messages container to bottom.
     */
    function scrollDmToBottom() {
        var container = document.querySelector('.dm-messages');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    /**
     * Get the chat container element (works for both desktop and mobile).
     * @returns {Element|null} Chat container element or null
     */
    function getChatContainer() {
        return document.querySelector('.chat-container') || document.querySelector('.mobile-chat-container');
    }

    /**
     * Get the currently active channel name from Alpine state.
     * @returns {string|null} Channel name or null if not available
     */
    function getActiveChannel() {
        var chatContainer = getChatContainer();
        if (!chatContainer) return null;

        // Try Alpine.$data first (preferred)
        if (typeof Alpine !== 'undefined' && Alpine.$data) {
            try {
                var data = Alpine.$data(chatContainer);
                if (data && data.activeChannel) {
                    return data.activeChannel;
                }
            } catch (e) {
                // Alpine not ready yet
            }
        }

        // Fallback: try _x_dataStack (internal Alpine)
        if (chatContainer._x_dataStack && chatContainer._x_dataStack[0]) {
            return chatContainer._x_dataStack[0].activeChannel || null;
        }

        return null;
    }

    /**
     * Get Alpine data from chat container.
     * @returns {Object|null} Alpine data object or null
     */
    function getAlpineData() {
        var chatContainer = getChatContainer();
        if (!chatContainer) return null;

        // Try Alpine.$data first (preferred)
        if (typeof Alpine !== 'undefined' && Alpine.$data) {
            try {
                var data = Alpine.$data(chatContainer);
                if (data) return data;
            } catch (e) {
                // Alpine not ready yet
            }
        }

        // Fallback: try _x_dataStack (internal Alpine)
        if (chatContainer._x_dataStack && chatContainer._x_dataStack[0]) {
            return chatContainer._x_dataStack[0];
        }

        return null;
    }

    /**
     * Get current user ID from chat container data attribute.
     * @returns {number|null} Current user ID or null
     */
    function getCurrentUserId() {
        var chatContainer = getChatContainer();
        if (chatContainer) {
            return parseInt(chatContainer.dataset.currentUserId) || null;
        }
        return window.CURRENT_USER_ID || null;
    }

    // =========================================================================
    // LocalStorage Functions for sparQy messages
    // =========================================================================

    function getAgentStorageKey() {
        var userId = getCurrentUserId();
        return userId ? AGENT_STORAGE_KEY_PREFIX + userId : null;
    }

    function getAgentMessages() {
        try {
            var key = getAgentStorageKey();
            if (!key) return [];
            var stored = localStorage.getItem(key);
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('Error reading agent messages from localStorage:', e);
            return [];
        }
    }

    function saveAgentMessages(messages) {
        try {
            var key = getAgentStorageKey();
            if (!key) return;
            localStorage.setItem(key, JSON.stringify(messages));
        } catch (e) {
            console.error('Error saving agent messages to localStorage:', e);
        }
    }

    /**
     * Add a message to localStorage for sparQy.
     * @param {Object} messageData - Message data object with html and metadata
     */
    function addAgentMessage(messageData) {
        var messages = getAgentMessages();
        messages.push({
            temp_id: messageData.temp_id,
            html: messageData.html,
            content: messageData.content,
            is_ai: messageData.is_ai,
            author_id: messageData.author_id,
            timestamp: new Date().toISOString()
        });
        saveAgentMessages(messages);
    }

    /**
     * Clear all agent messages from localStorage.
     */
    function clearAgentMessages() {
        try {
            var key = getAgentStorageKey();
            if (key) localStorage.removeItem(key);
            // Clean up old shared key from before per-user scoping
            localStorage.removeItem('sparq_agent_messages');
        } catch (e) {
            console.error('Error clearing agent messages from localStorage:', e);
        }
    }

    function loadAgentMessagesFromStorage() {
        var container = document.getElementById('agent-messages-container');
        if (!container) return;

        var messages = getAgentMessages();

        container.querySelectorAll('.message').forEach(function(el) { el.remove(); });

        if (messages.length === 0) return;

        messages.forEach(function(msg) {
            var wrapper = document.createElement('div');
            wrapper.innerHTML = msg.html;
            var messageDiv = wrapper.firstElementChild;
            if (messageDiv) {
                container.appendChild(messageDiv);
                htmx.process(messageDiv);
            }
        });

        container.scrollTop = container.scrollHeight;
    }

    // Expose to global scope for template script
    window.loadAgentMessagesFromStorage = loadAgentMessagesFromStorage;

    // =========================================================================
    // SocketIO Connection (deferred to avoid blocking page load)
    // =========================================================================

    var socket = null;
    var socketRetries = 0;
    var MAX_SOCKET_RETRIES = 10;

    function initSocket() {
        if (socket) return; // Already initialized

        // Safety check: ensure socket.io is loaded
        if (typeof io === 'undefined') {
            socketRetries++;
            if (socketRetries < MAX_SOCKET_RETRIES) {
                setTimeout(initSocket, 300);
            } else {
                window.SPARQ_DEBUG && console.log('Socket.io failed to load after retries, chat will work without real-time updates');
            }
            return;
        }

        try {
            socket = io('/sync', {
                transports: ['websocket'],
                reconnectionAttempts: 10,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 10000,
                timeout: 10000,
                forceNew: true
            });

            socket.on('connect', function() {
                window.SPARQ_DEBUG && console.log('Chat SocketIO connected');

                // Emit initial viewing state
                var alpineData = getAlpineData();
                if (alpineData) {
                    if (alpineData.activeView === 'dm' && alpineData.activeDmThread) {
                        socket.emit('viewing', { type: 'dm', id: alpineData.activeDmThread });
                    } else if (alpineData.activeChannel) {
                        socket.emit('viewing', { type: 'channel', id: alpineData.activeChannel });
                    }
                }
            });

            socket.on('disconnect', function() {
                window.SPARQ_DEBUG && console.log('Chat SocketIO disconnected');
            });

            socket.on('connect_error', function(error) {
                window.SPARQ_DEBUG && console.log('Chat SocketIO connection error:', error.message);
            });

            // Attach all event handlers after socket is created
            attachSocketHandlers(socket);
        } catch (e) {
            console.error('Failed to initialize socket:', e);
        }
    }

    /**
     * Disconnect socket to free browser connection slots.
     */
    function disconnectSocket() {
        if (socket) {
            socket.disconnect();
            socket = null;
        }
    }

    /**
     * Visibility-aware connection management.
     * Connect only when tab is visible to prevent Chrome's 6-connection-per-domain exhaustion.
     */
    function onVisibilityChange() {
        if (document.visibilityState === 'visible') {
            initSocket();
        } else {
            disconnectSocket();
        }
    }

    // Defer socket connection to after page is interactive (only if visible)
    if (document.readyState === 'complete') {
        if (document.visibilityState === 'visible') {
            setTimeout(initSocket, 100);
        }
    } else {
        window.addEventListener('load', function() {
            if (document.visibilityState === 'visible') {
                setTimeout(initSocket, 100);
            }
        });
    }

    document.addEventListener('visibilitychange', onVisibilityChange);

    /**
     * Attach all socket event handlers.
     * Called after socket is initialized.
     */
    function attachSocketHandlers(socket) {
        // =====================================================================
        // Channel Message Handlers
        // =====================================================================

        socket.on('new_message', function(data) {
            var activeChannel = getActiveChannel();
            var currentUserId = getCurrentUserId();

            if (data.channel === activeChannel) {
                var messagesContainer = document.getElementById('chat-messages');
                if (messagesContainer) {
                    var wrapper = document.createElement('div');
                    wrapper.innerHTML = data.html;
                    var messageDiv = wrapper.querySelector('.message');

                    if (messageDiv) {
                        var existingMsg = document.getElementById(messageDiv.id);
                        if (!existingMsg) {
                            // Check if this is our own message - look for optimistic messages to reconcile
                            if (data.author_id === currentUserId) {
                                var optimisticMessages = messagesContainer.querySelectorAll('.message.optimistic');
                                if (optimisticMessages.length > 0) {
                                    // Replace the oldest optimistic message with the real one
                                    var oldest = optimisticMessages[0];
                                    // Preserve continuation class if it was set
                                    if (oldest.classList.contains('continuation')) {
                                        messageDiv.classList.add('continuation');
                                    }
                                    oldest.replaceWith(messageDiv);
                                    htmx.process(messageDiv);
                                    // Remove 10-4 button on own message
                                    var ownTenFour = messageDiv.querySelector('.ten4-inline-btn');
                                    if (ownTenFour) ownTenFour.remove();
                                    return; // Don't append again
                                }
                            }

                            // Check if previous message is from same author (Slack-style grouping)
                            var lastMsg = messagesContainer.querySelector('.message:last-child');
                            if (lastMsg && lastMsg.dataset.authorId === messageDiv.dataset.authorId) {
                                messageDiv.classList.add('continuation');
                            }
                            messagesContainer.appendChild(messageDiv);
                            htmx.process(messageDiv);

                            // Remove 10-4 button if current user is the message author
                            // (broadcast renders button for all; filter client-side)
                            var tenFourBtn = messageDiv.querySelector('.ten4-inline-btn');
                            if (tenFourBtn && data.author_id === currentUserId) {
                                tenFourBtn.remove();
                            }

                            scrollToBottom();
                            fetch('/sync/chat/channels/' + data.channel + '/mark_read', {
                                method: 'POST',
                                credentials: 'same-origin'
                            });
                        }
                    }
                }
            } else {
                // Bold channel name for unread
                var channelEl = document.getElementById('channel-' + data.channel);
                if (channelEl) {
                    channelEl.classList.add('has-unread');
                }
                // Show @mention badge if current user is mentioned
                if (data.mentioned_user_ids && data.mentioned_user_ids.indexOf(window.CURRENT_USER_ID) !== -1) {
                    var mentionBadge = document.getElementById('mention-' + data.channel);
                    if (mentionBadge) {
                        var count = parseInt(mentionBadge.textContent || '0') + 1;
                        mentionBadge.textContent = count;
                        mentionBadge.style.display = 'flex';
                    } else {
                        // Create mention badge if it doesn't exist
                        var meta = channelEl ? channelEl.querySelector('.channel-meta') : null;
                        if (meta) {
                            mentionBadge = document.createElement('span');
                            mentionBadge.className = 'mention-badge';
                            mentionBadge.id = 'mention-' + data.channel;
                            mentionBadge.textContent = '1';
                            meta.insertBefore(mentionBadge, meta.firstChild);
                        }
                    }
                    // Track mention count for nav badge
                    var alpineMentionData = getAlpineData();
                    if (alpineMentionData && typeof alpineMentionData.unreadMentionCount !== 'undefined') {
                        alpineMentionData.unreadMentionCount++;
                    }
                }
                // Update mobile unread badge
                var mobileBadge = document.getElementById('unread-mobile-' + data.channel);
                if (mobileBadge) {
                    var mobileCount = parseInt(mobileBadge.textContent || '0') + 1;
                    mobileBadge.textContent = mobileCount;
                    mobileBadge.style.display = 'flex';
                } else {
                    // Create badge if channel had 0 unreads on page load
                    var channelBtn = document.querySelector('.channel-sheet-item[data-channel="' + data.channel + '"]');
                    if (channelBtn) {
                        mobileBadge = document.createElement('span');
                        mobileBadge.className = 'unread';
                        mobileBadge.id = 'unread-mobile-' + data.channel;
                        mobileBadge.textContent = '1';
                        channelBtn.appendChild(mobileBadge);
                    }
                }
                // Reorder channels to float notified channel up
                if (window.reorderMobileChannels) window.reorderMobileChannels();
                // Update unread channel count (works for both desktop and mobile)
                var alpineData = getAlpineData();
                if (alpineData && typeof alpineData.unreadChannelCount !== 'undefined') {
                    alpineData.unreadChannelCount++;
                }
                if (window.syncChatBadge) window.syncChatBadge();
                // Play notification sound for messages in other channels
                if (window.NotificationSound) {
                    window.NotificationSound.play();
                }
            }
        });

        socket.on('message_updated', function(data) {
            var wrapper = document.createElement('div');
            wrapper.innerHTML = data.html;
            var messageDiv = wrapper.querySelector('.message');
            if (messageDiv) {
                var existingMsg = document.getElementById(messageDiv.id);
                if (existingMsg) {
                    existingMsg.replaceWith(messageDiv);
                    htmx.process(messageDiv);
                }
            }
        });

        socket.on('message_deleted', function(data) {
            var msgEl = document.getElementById('message-' + data.message_id);
            if (msgEl) msgEl.remove();
        });

        socket.on('reaction_update', function(data) {
            // Update reaction UI for all users viewing this channel
            var activeChannel = getActiveChannel();
            if (data.channel === activeChannel) {
                if (typeof window.updateReactionsUI === 'function') {
                    window.updateReactionsUI(data.message_id, data.reactions);
                }
            }
        });

        socket.on('ten_four_update', function(data) {
            var activeChannel = getActiveChannel();
            if (data.channel === activeChannel) {
                if (typeof window.updateTenFourUI === 'function') {
                    window.updateTenFourUI(data.message_id, data.ack_data);
                }
            }
        });

        socket.on('clear_messages', function(data) {
            var currentUserId = getCurrentUserId();

            if (data.user_id && data.user_id !== currentUserId) {
                return;
            }

            if (data.sparqy) {
                clearAgentMessages();
                var alpineData = getAlpineData();
                if (alpineData && alpineData.activeDmUser === 'sparqy') {
                    var agentContainer = document.getElementById('agent-messages-container');
                    if (agentContainer) {
                        agentContainer.querySelectorAll('.message').forEach(function(el) { el.remove(); });
                    }
                }
                return;
            }

            var activeChannel = getActiveChannel();
            if (data.channel === activeChannel) {
                var messagesContainer = document.getElementById('chat-messages');
                if (messagesContainer) {
                    messagesContainer.innerHTML = '';
                }
            }
        });

        socket.on('agent_message', function(data) {
            var currentUserId = getCurrentUserId();

            if (currentUserId) {
                var isMyMessage = data.author_id === currentUserId;
                var isForMe = data.target_user_id === currentUserId;
                if (!isMyMessage && !isForMe) {
                    return;
                }
            }

            if (data.clear_storage) {
                clearAgentMessages();
                var alpineData = getAlpineData();
                if (alpineData && alpineData.activeDmUser === 'sparqy') {
                    var agentContainer = document.getElementById('agent-messages-container');
                    if (agentContainer) {
                        agentContainer.querySelectorAll('.message').forEach(function(el) { el.remove(); });
                    }
                }
            }

            addAgentMessage(data);

            document.dispatchEvent(new CustomEvent('dm-popup-sparqy-message'));

            var alpineData = getAlpineData();
            if (alpineData && alpineData.activeDmUser === 'sparqy') {
                var agentContainer = document.getElementById('agent-messages-container');
                if (agentContainer) {
                    var wrapper = document.createElement('div');
                    wrapper.innerHTML = data.html;
                    var messageDiv = wrapper.firstElementChild;
                    if (messageDiv) {
                        var existingMsg = agentContainer.querySelector('[data-temp-id="' + data.temp_id + '"]');
                        if (!existingMsg) {
                            agentContainer.appendChild(messageDiv);
                            htmx.process(messageDiv);
                            agentContainer.scrollTop = agentContainer.scrollHeight;
                        }
                    }
                }
            }
        });

        // =====================================================================
        // Channel Handlers
        // =====================================================================

        socket.on('channel_created', function(data) {
            socket.emit('join_channel', { channel: data.channel });

            // Desktop: append to channel list and reorder
            var channelList = document.getElementById('channel-list');
            if (channelList) {
                var wrapper = document.createElement('div');
                wrapper.innerHTML = data.html;
                var channelDiv = wrapper.querySelector('.channel');
                if (channelDiv) {
                    channelList.appendChild(channelDiv);
                    htmx.process(channelDiv);
                }
            }

            // Mobile: append to channel sheet and reorder
            var channelSheet = document.querySelector('.channel-sheet-content');
            if (channelSheet) {
                var btn = document.createElement('button');
                btn.className = 'channel-sheet-item';
                btn.setAttribute('data-channel', data.channel);
                var safeChannel = data.channel.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                btn.innerHTML = '<span><span class="channel-prefix">#</span>' + safeChannel + '</span>';
                btn.addEventListener('click', function() {
                    var chatContainer = getChatContainer();
                    if (chatContainer && chatContainer._x_dataStack && chatContainer._x_dataStack[0]) {
                        chatContainer._x_dataStack[0].selectChannel(data.channel);
                    }
                });
                channelSheet.appendChild(btn);
                reorderMobileChannels();
            }
        });

        socket.on('channel_deleted', function(data) {
            var channelEl = document.getElementById('channel-' + data.channel);
            if (channelEl) channelEl.remove();
            // Update remaining channel slots
            var alpineData = getAlpineData();
            if (alpineData && typeof alpineData.remainingChannelSlots === 'number') {
                alpineData.remainingChannelSlots++;
            }
        });

        // =====================================================================
        // Presence Handlers
        // =====================================================================

        socket.on('presence_update', function(data) {
            var indicator = document.getElementById('presence-' + data.user_id);
            if (indicator) {
                indicator.className = 'presence-indicator ' + data.status;
                indicator.title = data.status.charAt(0).toUpperCase() + data.status.slice(1);
            }
        });

        // =====================================================================
        // Direct Message Handlers
        // =====================================================================

        socket.on('new_dm', function(data) {
            var alpineData = getAlpineData();
            if (!alpineData) return;

            var isMobile = !!document.querySelector('.mobile-chat-container');
            var isFromOther = data.sender_id === data.other_user_id;

            if (alpineData.activeView === 'dm' && alpineData.activeDmThread === data.thread_id) {
                var container = document.querySelector('.dm-messages');
                if (container) {
                    var wrapper = document.createElement('div');
                    wrapper.innerHTML = data.html;
                    var msgDiv = wrapper.querySelector('.dm-message');
                    if (msgDiv) {
                        // Check if message already exists (avoid duplicates)
                        if (!document.getElementById(msgDiv.id)) {
                            // Check if previous message is from same author (Slack-style grouping)
                            var lastDmMsg = container.querySelector('.dm-message:last-child');
                            if (lastDmMsg && lastDmMsg.dataset.authorId === msgDiv.dataset.authorId) {
                                msgDiv.classList.add('continuation');
                            }
                            container.appendChild(msgDiv);
                            htmx.process(msgDiv);
                            scrollDmToBottom();
                        }
                        if (isFromOther) {
                            fetch('/sync/chat/dms/' + data.thread_id + '/read', {
                                method: 'POST',
                                credentials: 'same-origin'
                            });
                        }
                    }
                }
            } else if (isFromOther) {
                // Message from someone else and not viewing that DM - increment unread
                if (typeof alpineData.unreadDmCount !== 'undefined') {
                    alpineData.unreadDmCount++;
                }
                if (window.syncChatBadge) window.syncChatBadge();
                // Play notification sound for DMs not currently being viewed
                if (window.NotificationSound) {
                    window.NotificationSound.play();
                }
            }

            // Update DM list (desktop only - mobile list is in bottom sheet)
            if (!isMobile && document.getElementById('dm-list')) {
                htmx.ajax('GET', '/sync/chat/dms', '#dm-list');
            }

            // Let the FAB popup piggyback on this connection on chat pages
            // (popup skips its own socket when pathname starts with /sync/chat).
            document.dispatchEvent(new CustomEvent('dm-popup-new-message', { detail: data }));
        });

        socket.on('dm_deleted', function(data) {
            var msgEl = document.getElementById('dm-message-' + data.message_id);
            if (msgEl) {
                msgEl.remove();
            }
        });

        socket.on('dm_reaction_update', function(data) {
            if (typeof window.updateDmReactionsUI === 'function') {
                window.updateDmReactionsUI(data.message_id, data.reactions);
            }
        });

        // =====================================================================
        // Typing Indicator Handlers
        // =====================================================================

        socket.on('user_typing', function(data) {
            var alpineData = getAlpineData();
            if (alpineData && alpineData.activeView === 'dm') return;
            var activeChannel = getActiveChannel();
            if (data.channel !== activeChannel) return;

            // Track this user as typing
            if (!typingUsers.channel) typingUsers.channel = {};
            if (!typingUsers.channel[data.channel]) typingUsers.channel[data.channel] = {};

            // Clear existing timeout for this user
            if (typingUsers.channel[data.channel][data.user_id]) {
                clearTimeout(typingUsers.channel[data.channel][data.user_id].timeout);
            }

            // Set new timeout to clear typing
            var timeoutId = setTimeout(function() {
                delete typingUsers.channel[data.channel][data.user_id];
                updateTypingIndicator('channel', data.channel);
            }, TYPING_TIMEOUT_MS);

            typingUsers.channel[data.channel][data.user_id] = {
                name: data.user_name,
                timeout: timeoutId
            };

            updateTypingIndicator('channel', data.channel);
        });

        socket.on('user_stop_typing', function(data) {
            if (typingUsers.channel && typingUsers.channel[data.channel] && typingUsers.channel[data.channel][data.user_id]) {
                clearTimeout(typingUsers.channel[data.channel][data.user_id].timeout);
                delete typingUsers.channel[data.channel][data.user_id];
                updateTypingIndicator('channel', data.channel);
            }
        });

        socket.on('user_typing_dm', function(data) {
            var alpineData = getAlpineData();
            if (!alpineData || alpineData.activeView !== 'dm') return;
            if (alpineData.activeDmThread !== data.thread_id) return;

            // Track this user as typing in DM
            if (!typingUsers.dm) typingUsers.dm = {};
            if (!typingUsers.dm[data.thread_id]) typingUsers.dm[data.thread_id] = {};

            if (typingUsers.dm[data.thread_id][data.user_id]) {
                clearTimeout(typingUsers.dm[data.thread_id][data.user_id].timeout);
            }

            var timeoutId = setTimeout(function() {
                delete typingUsers.dm[data.thread_id][data.user_id];
                updateTypingIndicator('dm', data.thread_id);
            }, TYPING_TIMEOUT_MS);

            typingUsers.dm[data.thread_id][data.user_id] = {
                name: data.user_name,
                timeout: timeoutId
            };

            updateTypingIndicator('dm', data.thread_id);
        });

        socket.on('user_stop_typing_dm', function(data) {
            if (typingUsers.dm && typingUsers.dm[data.thread_id] && typingUsers.dm[data.thread_id][data.user_id]) {
                clearTimeout(typingUsers.dm[data.thread_id][data.user_id].timeout);
                delete typingUsers.dm[data.thread_id][data.user_id];
                updateTypingIndicator('dm', data.thread_id);
            }
        });
    }

    // =========================================================================
    // Typing Indicator Functions
    // =========================================================================

    /**
     * Update the typing indicator UI.
     * @param {string} type - 'channel' or 'dm'
     * @param {string|number} id - channel name or thread ID
     */
    function updateTypingIndicator(type, id) {
        var indicator = type === 'dm'
            ? document.getElementById('dm-typing-indicator')
            : document.getElementById('typing-indicator');
        if (!indicator) return;

        var users = [];
        if (type === 'channel' && typingUsers.channel && typingUsers.channel[id]) {
            users = Object.values(typingUsers.channel[id]).map(function(u) { return u.name; });
        } else if (type === 'dm' && typingUsers.dm && typingUsers.dm[id]) {
            users = Object.values(typingUsers.dm[id]).map(function(u) { return u.name; });
        }

        if (users.length === 0) {
            indicator.style.display = 'none';
            indicator.innerHTML = '';
            return;
        }

        var text = '';
        if (users.length === 1) {
            text = users[0] + ' is typing';
        } else if (users.length === 2) {
            text = users[0] + ' and ' + users[1] + ' are typing';
        } else {
            text = users[0] + ' and ' + (users.length - 1) + ' others are typing';
        }

        indicator.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span> ' + text;
        indicator.style.display = 'flex';
    }

    /**
     * Emit typing event when user starts typing.
     * @param {string} type - 'channel' or 'dm'
     * @param {string|number} id - channel name or thread ID
     */
    function emitTyping(type, id) {
        if (!socket || !socket.connected) return;

        // Clear existing timeout
        if (typingTimeout) {
            clearTimeout(typingTimeout);
        }

        // Emit typing event
        if (type === 'channel') {
            socket.emit('typing', { channel: id });
        } else if (type === 'dm') {
            socket.emit('typing', { dm_thread_id: id });
        }

        // Set timeout to emit stop_typing
        typingTimeout = setTimeout(function() {
            emitStopTyping(type, id);
        }, TYPING_TIMEOUT_MS);
    }

    /**
     * Emit stop typing event.
     * @param {string} type - 'channel' or 'dm'
     * @param {string|number} id - channel name or thread ID
     */
    function emitStopTyping(type, id) {
        if (!socket || !socket.connected) return;

        if (typingTimeout) {
            clearTimeout(typingTimeout);
            typingTimeout = null;
        }

        if (type === 'channel') {
            socket.emit('stop_typing', { channel: id });
        } else if (type === 'dm') {
            socket.emit('stop_typing', { dm_thread_id: id });
        }
    }

    /**
     * Clear typing indicator when switching channels/DMs.
     */
    function clearTypingIndicator() {
        var indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.style.display = 'none';
            indicator.innerHTML = '';
        }
    }

    // Expose typing functions globally
    window.emitTyping = emitTyping;
    window.emitStopTyping = emitStopTyping;
    window.clearTypingIndicator = clearTypingIndicator;

    /**
     * Emit viewing event to track which channel/DM the user is viewing.
     * This is used to suppress push notifications when actively viewing.
     * @param {string} type - 'channel' or 'dm'
     * @param {string|number} id - channel name or thread ID
     */
    function emitViewing(type, id) {
        if (!socket || !socket.connected) return;
        socket.emit('viewing', { type: type, id: id });
    }

    /**
     * Clear viewing state (user left chat).
     */
    function clearViewing() {
        if (!socket || !socket.connected) return;
        socket.emit('viewing', {});
    }

    // Expose viewing functions globally
    window.emitViewing = emitViewing;
    window.clearViewing = clearViewing;

    // =========================================================================
    // Heartbeat (runs independently, checks if socket exists)
    // =========================================================================

    setInterval(function() {
        if (socket && socket.connected) {
            socket.emit('heartbeat');
        }
    }, 60000);

    // Scroll to bottom after initial load and channel switches
    document.body.addEventListener('htmx:afterRequest', function(event) {
        try {
            if (event.detail && event.detail.target && event.detail.target.id === 'chat-messages') {
                // Skip scroll-to-bottom when loading older messages
                var requestUrl = (event.detail.pathInfo && event.detail.pathInfo.requestPath) || (event.detail.requestConfig && event.detail.requestConfig.path) || '';
                if (requestUrl.indexOf('before_id') !== -1) {
                    return;
                }
                // Check if DM view is loaded, scroll appropriate container
                if (document.querySelector('.dm-view')) {
                    scrollDmToBottom();
                } else {
                    var alpineData = getAlpineData();
                    if (alpineData && alpineData.activeDmUser === 'sparqy') {
                        setTimeout(function() {
                            loadAgentMessagesFromStorage();
                        }, 50);
                    } else {
                        scrollToBottom();
                    }
                }
            }
        } catch (e) {
            console.error('Error in htmx:afterRequest handler:', e);
        }
    });

    // =========================================================================
    // Exposed Helpers for HTMX-loaded Content
    // =========================================================================

    /**
     * Select a DM thread - called from HTMX-loaded _dm_list.html partial.
     * Updates Alpine state and manages active class for highlighting.
     * @param {HTMLElement} el - The clicked DM item element
     * @param {number} otherId - The other user's ID
     * @param {number} threadId - The DM thread ID
     */
    window.selectDmThread = function(el, otherId, threadId, unreadCount) {
        // Clear typing indicator when switching
        clearTypingIndicator();

        var c = getChatContainer();
        if (c && c._x_dataStack) {
            var data = c._x_dataStack[0];
            data.activeView = 'dm';
            data.activeChannel = null;
            data.activeDmUser = otherId;
            data.activeDmThread = threadId;

            // Emit viewing event for push notification suppression
            emitViewing('dm', threadId);

            // Read actual unread count from DOM badge (more reliable than parameter)
            var unreadBadge = document.getElementById('dm-unread-' + threadId);
            var actualUnread = unreadBadge ? parseInt(unreadBadge.textContent || '0') : unreadCount;

            if (actualUnread > 0 && data.unreadDmCount > 0) {
                data.unreadDmCount = Math.max(0, data.unreadDmCount - actualUnread);
            }

            // Remove badge element
            if (unreadBadge) unreadBadge.remove();

            // Always sync badge after DM selection
            window.syncChatBadge();
        }
        document.querySelectorAll('.dm-item').forEach(function(item) {
            item.classList.remove('active');
        });
        el.classList.add('active');
        el.classList.remove('has-unread');
    };

    /**
     * Sync the desktop/PWA badge with current unread counts.
     * Call this after any operation that changes unread state.
     */
    window.syncChatBadge = function() {
        var c = getChatContainer();
        if (!c || !c._x_dataStack) return;

        var data = c._x_dataStack[0];
        var total = (data.unreadChannelCount || 0) + (data.unreadDmCount || 0);
        var importantCount = (data.unreadDmCount || 0) + (data.unreadMentionCount || 0);

        window.SPARQ_DEBUG && console.log('[Badge] syncChatBadge called, total:', total, 'important:', importantCount);

        // Update nav sidebar badge (data-chat-badge elements)
        // Show count for DMs/mentions, plain dot for regular channel unreads
        document.querySelectorAll('[data-chat-badge]').forEach(function(el) {
            if (total > 0) {
                el.style.display = '';
                el.textContent = importantCount > 0 ? (importantCount > 99 ? '99+' : importantCount) : '';
            } else {
                el.style.display = 'none';
                el.textContent = '';
            }
        });

        if (window.updateDesktopBadge) {
            window.updateDesktopBadge(total);
        }

        // Explicitly clear PWA badge if total is 0
        if (total === 0 && navigator.clearAppBadge) {
            navigator.clearAppBadge()
                .then(function() { window.SPARQ_DEBUG && console.log('[Badge] PWA badge explicitly cleared'); })
                .catch(function() {});
        }
    };

    /**
     * Get current total unread count from Alpine state.
     */
    window.getChatUnreadCount = function() {
        var c = getChatContainer();
        if (!c || !c._x_dataStack) return 0;
        var data = c._x_dataStack[0];
        return (data.unreadChannelCount || 0) + (data.unreadDmCount || 0);
    };

    // Close socket on page unload to free browser connection slots
    window.addEventListener('beforeunload', disconnectSocket);

})();
