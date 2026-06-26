document.addEventListener('DOMContentLoaded', () => {
    const chatArea = document.getElementById('chat-area');
    const commandInput = document.getElementById('command-input');
    const sendBtn = document.getElementById('send-btn');
    const statusIndicator = document.querySelector('.status-indicator');

    // Status display element
    let statusEl = document.getElementById('status-text');
    if (!statusEl) {
        statusEl = document.createElement('div');
        statusEl.id = 'status-text';
        statusEl.style.cssText = 'text-align:center; color:#888; font-size:0.85em; padding:4px 0; min-height:1.2em; transition: opacity 0.3s;';
        const inputArea = document.querySelector('.input-area') || chatArea.parentElement;
        inputArea.parentElement.insertBefore(statusEl, inputArea);
    }

    // Status label map
    const STATUS_LABELS = {
        'listening': '👂 Listening for wake word...',
        'listening_command': '🎤 Listening for command...',
        'thinking': '🧠 Thinking...',
        'processing': '⚙️ Processing...',
        'executing': '⚡ Executing...',
        'responding': '💬 Responding...',
        'idle': '',
    };

    function setStatus(status) {
        const label = STATUS_LABELS[status] || status;
        if (statusEl) {
            statusEl.textContent = label;
            statusEl.style.opacity = label ? '1' : '0';
        }
    }

    // Establish WebSocket Connection
    let wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
    let ws = null;
    let reconnectDelay = 1000;

    function connectWS() {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            statusIndicator.style.backgroundColor = '#4CAF50';
            statusIndicator.style.boxShadow = '0 0 8px #4CAF50';
            reconnectDelay = 1000;
        };

        ws.onclose = () => {
            statusIndicator.style.backgroundColor = '#f44336';
            statusIndicator.style.boxShadow = '0 0 8px #f44336';
            // Auto-reconnect with exponential backoff
            setTimeout(connectWS, Math.min(reconnectDelay, 10000));
            reconnectDelay *= 2;
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.event === 'status') {
                    setStatus(data.status || '');
                } else if (data.event === 'user_command') {
                    addMessage(data.text, 'user');
                    setStatus('thinking');
                } else if (data.event === 'response') {
                    addMessage(data.text, 'assistant');
                    setStatus('');
                } else if (data.event === 'perf') {
                    // Show performance summary in a subtle way
                    if (data.metrics) {
                        const total = data.metrics.total_ms;
                        const route = data.metrics.route;
                        console.log(`[Perf] ${route}: ${total}ms`, data.metrics);
                    }
                } else if (data.text) {
                    addMessage(data.text, 'assistant');
                }
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };
    }

    connectWS();

    // Send command handler
    const sendCommand = async () => {
        const text = commandInput.value.trim();
        if (!text) return;

        // Add user message to UI
        addMessage(text, 'user');
        commandInput.value = '';
        setStatus('thinking');

        try {
            const res = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: text })
            });
            const data = await res.json();
            if (!data.success) {
                addMessage('Error: ' + data.message, 'system');
                setStatus('');
            }
        } catch (e) {
            addMessage('Network error while sending command.', 'system');
            setStatus('');
        }
    };

    // Event Listeners
    sendBtn.addEventListener('click', sendCommand);
    commandInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendCommand();
    });

    // Helper: Add message to DOM
    function addMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message');
        
        if (sender === 'user') {
            msgDiv.classList.add('user-message');
        } else if (sender === 'assistant') {
            msgDiv.classList.add('assistant-message');
        } else {
            msgDiv.classList.add('system-message');
        }
        
        msgDiv.textContent = text;
        chatArea.appendChild(msgDiv);
        chatArea.scrollTop = chatArea.scrollHeight;
    }
});
