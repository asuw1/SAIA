/**
 * SAIA V4 Chat Module
 * Handles chat interface and streaming responses
 */

class ChatManager {
    constructor() {
        this.sessionId = null;
        this.messages = [];
        this.isStreaming = false;
        this.suggestedPrompts = [
            'Show me all critical alerts from this week',
            'What is the current anomaly score threshold?',
            'List all false positive cases',
            'Generate a compliance report for NCA',
            'What rules are currently active?',
            'Show alerts by severity distribution'
        ];
    }

    /**
     * Initialize chat session
     */
    async initSession() {
        try {
            const response = await saia.createChatSession();
            this.sessionId = response.session_id || response.id;
            this.messages = [];
            this.renderChat();
            return this.sessionId;
        } catch (error) {
            console.error('Error creating chat session:', error);
            showToast('Failed to initialize chat session', 'error');
            return null;
        }
    }

    /**
     * Send message to chat
     */
    async sendMessage(message) {
        if (!message.trim() || !this.sessionId) return;

        // Clear input
        const inputField = document.querySelector('.chat-input');
        if (inputField) inputField.value = '';

        // Add user message to UI
        this.addUserMessage(message);

        // Get streaming response
        await this.getStreamingResponse(message);
    }

    /**
     * Get streaming response from API
     */
    async getStreamingResponse(message) {
        this.isStreaming = true;
        let assistantMessage = '';

        // Add streaming indicator
        const messageBubble = this.addAssistantMessage('');
        const indicator = messageBubble.querySelector('.streaming-indicator');

        try {
            // Use streaming if available
            let fullResponse = '';
            if (saia.streamChatResponse) {
                for await (const chunk of saia.streamChatResponse(this.sessionId, message)) {
                    if (chunk.text) {
                        fullResponse += chunk.text;
                        assistantMessage = this.markdownToHtml(fullResponse);
                        if (messageBubble) {
                            const contentDiv = messageBubble.querySelector('.message-content') || messageBubble;
                            contentDiv.innerHTML = assistantMessage;
                        }
                    }

                    // Handle sources
                    if (chunk.sources) {
                        this.renderSources(messageBubble, chunk.sources);
                    }
                }
            } else {
                // Fallback to regular request
                const response = await saia.sendChatMessage(this.sessionId, message);
                assistantMessage = this.markdownToHtml(response.response);
                if (messageBubble) {
                    const contentDiv = messageBubble.querySelector('.message-content') || messageBubble;
                    contentDiv.innerHTML = assistantMessage;
                }

                if (response.sources) {
                    this.renderSources(messageBubble, response.sources);
                }
            }

            // Remove streaming indicator
            if (indicator) indicator.remove();

            // Store message
            this.messages.push({
                role: 'assistant',
                content: assistantMessage,
                timestamp: new Date()
            });

            this.scrollToBottom();
        } catch (error) {
            console.error('Error getting chat response:', error);
            if (messageBubble) {
                messageBubble.innerHTML = '<p style="color: #ef4444;">Error: Could not generate response. Please try again.</p>';
            }
        } finally {
            this.isStreaming = false;
        }
    }

    /**
     * Add user message to chat
     */
    addUserMessage(content) {
        const messagesContainer = document.querySelector('.chat-messages');
        if (!messagesContainer) return null;

        const message = document.createElement('div');
        message.className = 'message user';
        message.innerHTML = `
            <div class="message-bubble">${escapeHtml(content)}</div>
        `;

        messagesContainer.appendChild(message);
        this.messages.push({
            role: 'user',
            content,
            timestamp: new Date()
        });

        this.scrollToBottom();
        return message;
    }

    /**
     * Add assistant message to chat
     */
    addAssistantMessage(content) {
        const messagesContainer = document.querySelector('.chat-messages');
        if (!messagesContainer) return null;

        const message = document.createElement('div');
        message.className = 'message assistant';
        message.innerHTML = `
            <div class="message-bubble">
                ${content ? this.markdownToHtml(content) : '<div class="streaming-indicator"><div class="streaming-dot"></div><div class="streaming-dot"></div><div class="streaming-dot"></div></div>'}
            </div>
        `;

        messagesContainer.appendChild(message);
        this.scrollToBottom();
        return message;
    }

    /**
     * Render sources/citations
     */
    renderSources(messageBubble, sources) {
        if (!messageBubble || !sources || sources.length === 0) return;

        let sourcesHtml = '<div class="message-sources">';
        sources.forEach((source, index) => {
            sourcesHtml += `<a href="#" class="message-source" data-source="${source.id}" data-type="${source.type}">${source.title}</a>`;
        });
        sourcesHtml += '</div>';

        const sourcesDiv = document.createElement('div');
        sourcesDiv.innerHTML = sourcesHtml;

        messageBubble.appendChild(sourcesDiv);

        // Add click handlers
        sourcesDiv.querySelectorAll('.message-source').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const sourceId = link.dataset.source;
                const sourceType = link.dataset.type;
                this.navigateToSource(sourceType, sourceId);
            });
        });
    }

    /**
     * Navigate to source (alert, rule, case, etc.)
     */
    navigateToSource(type, id) {
        const routes = {
            'alert': `/pages/alert-detail.html?id=${id}`,
            'rule': `/pages/rules.html?id=${id}`,
            'case': `/pages/cases.html?id=${id}`,
            'report': `/pages/reports.html?id=${id}`
        };

        if (routes[type]) {
            window.location.href = routes[type];
        }
    }

    /**
     * Convert markdown to HTML
     */
    markdownToHtml(markdown) {
        let html = escapeHtml(markdown);

        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Italic
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // Code inline
        html = html.replace(/`(.*?)`/g, '<code style="background-color: rgba(59, 130, 246, 0.1); padding: 2px 6px; border-radius: 3px; font-family: monospace;">$1</code>');

        // Code blocks
        html = html.replace(/```(.*?)```/gs, '<pre style="background-color: rgba(0, 0, 0, 0.3); padding: 10px; border-radius: 4px; overflow-x: auto;"><code>$1</code></pre>');

        // Links
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color: #3b82f6; text-decoration: underline;" target="_blank">$1</a>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Scroll to bottom of messages
     */
    scrollToBottom() {
        const messagesContainer = document.querySelector('.chat-messages');
        if (messagesContainer) {
            setTimeout(() => {
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }, 100);
        }
    }

    /**
     * Clear chat history
     */
    clearChat() {
        const messagesContainer = document.querySelector('.chat-messages');
        if (messagesContainer) {
            messagesContainer.innerHTML = '';
        }
        this.messages = [];
        this.initSession();
    }

    /**
     * Render chat UI
     */
    renderChat() {
        const chatPanel = document.querySelector('.chat-panel');
        if (!chatPanel) {
            console.warn('Chat panel not found');
            return;
        }

        // Ensure chat messages container exists
        if (!document.querySelector('.chat-messages')) {
            const messagesDiv = document.createElement('div');
            messagesDiv.className = 'chat-messages';
            chatPanel.insertBefore(messagesDiv, chatPanel.querySelector('.chat-input-area'));
        }

        // Add suggested prompts if no messages yet
        if (this.messages.length === 0) {
            this.renderSuggestedPrompts();
        }
    }

    /**
     * Render suggested prompts
     */
    renderSuggestedPrompts() {
        const messagesContainer = document.querySelector('.chat-messages');
        if (!messagesContainer || this.messages.length > 0) return;

        const suggestedDiv = document.createElement('div');
        suggestedDiv.style.cssText = `
            padding: 20px;
            text-align: center;
            color: #9ca3af;
        `;

        suggestedDiv.innerHTML = `
            <div style="margin-bottom: 20px; font-size: 14px; color: #d1d5db;">
                <strong>Suggested Queries:</strong>
            </div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
                ${this.suggestedPrompts.slice(0, 3).map(prompt => `
                    <button class="suggested-prompt-btn" style="
                        background-color: rgba(59, 130, 246, 0.1);
                        border: 1px solid rgba(59, 130, 246, 0.3);
                        color: #3b82f6;
                        padding: 10px 15px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 13px;
                        transition: all 150ms;
                        text-align: left;
                    " onclick="chatManager.sendMessage('${prompt.replace(/'/g, "\\'")}')">${prompt}</button>
                `).join('')}
            </div>
        `;

        messagesContainer.appendChild(suggestedDiv);
    }
}

/**
 * Utility: Escape HTML
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Initialize chat UI
 */
function initializeChatUI() {
    const chatToggleBtn = document.getElementById('chatToggleBtn') || document.querySelector('[data-chat-toggle]');
    const chatPanel = document.querySelector('.chat-panel');
    const chatCloseBtn = document.querySelector('.chat-close');

    if (chatToggleBtn && chatPanel) {
        chatToggleBtn.addEventListener('click', () => {
            chatPanel.classList.toggle('active');
            if (chatPanel.classList.contains('active') && !chatManager.sessionId) {
                chatManager.initSession();
            }
        });
    }

    if (chatCloseBtn && chatPanel) {
        chatCloseBtn.addEventListener('click', () => {
            chatPanel.classList.remove('active');
        });
    }

    // Chat input handler
    const chatInput = document.querySelector('.chat-input');
    const chatSendBtn = document.querySelector('.chat-send');

    if (chatInput && chatSendBtn) {
        const sendMessage = () => {
            if (!chatManager.isStreaming) {
                const message = chatInput.value.trim();
                if (message) {
                    chatManager.sendMessage(message);
                }
            }
        };

        chatSendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Clear chat button
    const chatClearBtn = document.querySelector('[data-chat-clear]');
    if (chatClearBtn) {
        chatClearBtn.addEventListener('click', () => {
            if (confirm('Clear chat history?')) {
                chatManager.clearChat();
            }
        });
    }
}

// Global chat manager instance
const chatManager = new ChatManager();

// Export for modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChatManager, initializeChatUI, escapeHtml };
}
