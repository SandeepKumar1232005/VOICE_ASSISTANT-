document.addEventListener('DOMContentLoaded', () => {
    const chatArea = document.getElementById('chat-area');
    const commandInput = document.getElementById('command-input');
    const sendBtn = document.getElementById('send-btn');
    const statusIndicator = document.querySelector('.status-indicator');

    // Establish WebSocket Connection
    let wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws';
    let ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        statusIndicator.style.backgroundColor = '#4CAF50';
        statusIndicator.style.boxShadow = '0 0 8px #4CAF50';
    };

    ws.onclose = () => {
        statusIndicator.style.backgroundColor = '#f44336';
        statusIndicator.style.boxShadow = '0 0 8px #f44336';
        addMessage('System disconnected.', 'system');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.event === 'status') {
                // Could show typing indicator here
            } else if (data.text) {
                addMessage(data.text, 'assistant');
            }
        } catch (e) {
            console.error('Error parsing WS message:', e);
        }
    };

    // Send command handler
    const sendCommand = async () => {
        const text = commandInput.value.trim();
        if (!text) return;

        // Add user message to UI
        addMessage(text, 'user');
        commandInput.value = '';

        try {
            const res = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: text })
            });
            const data = await res.json();
            if (!data.success) {
                addMessage('Error: ' + data.message, 'system');
            }
        } catch (e) {
            addMessage('Network error while sending command.', 'system');
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
