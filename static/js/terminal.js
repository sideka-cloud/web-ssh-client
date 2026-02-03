// Terminal JavaScript for SSH connections

class WebSSHTerminal {
    constructor() {
        this.term = null;
        this.socket = null;
        this.connectionId = null;
        this.sshConnectionId = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        
        this.init();
    }
    
    init() {
        // Get connection ID from hidden input
        this.connectionId = document.getElementById('connectionId').value;
        const connectionData = JSON.parse(document.getElementById('connectionData').value);
        
        // Initialize terminal
        this.initializeTerminal();
        
        // Initialize Socket.IO connection
        this.initializeSocket();
        
        // Connect to SSH
        this.connectToSSH(connectionData);
        
        // Setup event listeners
        this.setupEventListeners();
    }
    
    initializeTerminal() {
        // Load xterm addons
        const { Terminal } = window;
        const { FitAddon } = window.FitAddon;
        
        // Create terminal
        this.term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#00ff00',
                cursor: '#00ff00',
                selection: 'rgba(0, 255, 0, 0.3)'
            }
        });
        
        // Create addons
        this.fitAddon = new FitAddon();
        
        // Load addons
        this.term.loadAddon(this.fitAddon);
        
        // Open terminal in container
        this.term.open(document.getElementById('terminal-container'));
        
        // Fit terminal to container
        this.fitAddon.fit();
        
        // Handle terminal resize
        window.addEventListener('resize', () => {
            this.fitAddon.fit();
            if (this.socket && this.sshConnectionId) {
                const dims = this.fitAddon.proposeDimensions();
                if (dims) {
                    this.socket.emit('resize', {
                        connection_id: this.sshConnectionId,
                        rows: dims.rows,
                        cols: dims.cols
                    });
                }
            }
        });
        
        // Handle terminal input
        this.term.onData(data => {
            this.handleTerminalInput(data);
        });
        
        // Handle paste
        this.term.onKey(e => {
            if (e.domEvent.ctrlKey && e.domEvent.key === 'v') {
                navigator.clipboard.readText().then(text => {
                    this.sendInput(text);
                });
            }
        });
        
        // Write welcome message
        this.term.writeln('\x1b[1;32mWeb SSH Client Terminal\x1b[0m');
        this.term.writeln('\x1b[1;36mConnecting to SSH server...\x1b[0m');
        this.term.writeln('');
    }
    
    initializeSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('WebSocket connected');
            this.updateStatus('Connecting...', 'warning');
        });
        
        this.socket.on('ssh_connected', (data) => {
            console.log('SSH connected:', data);
            this.sshConnectionId = data.connection_id;
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.updateStatus('Connected', 'success');
            
            // Clear terminal and show welcome
            this.term.clear();
            this.term.writeln('\x1b[1;32m✓ SSH Connection Established\x1b[0m');
            this.term.writeln('\x1b[1;36mYou can now run commands...\x1b[0m');
            this.term.writeln('');
            this.term.focus();
        });
        
        this.socket.on('ssh_output', (data) => {
            if (data.connection_id === this.sshConnectionId) {
                this.term.write(data.data);
            }
        });
        
        this.socket.on('ssh_error', (data) => {
            this.term.writeln(`\x1b[1;31m✗ SSH Error: ${data.message}\x1b[0m`);
            this.updateStatus('Connection Failed', 'danger');
            this.isConnected = false;
        });
        
        this.socket.on('ssh_disconnected', (data) => {
            this.term.writeln(`\x1b[1;33m⚠ SSH Disconnected: ${data.message}\x1b[0m`);
            this.updateStatus('Disconnected', 'secondary');
            this.isConnected = false;
            this.sshConnectionId = null;
        });
        
        this.socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
            this.updateStatus('Disconnected', 'danger');
            this.isConnected = false;
        });
    }
    
    connectToSSH(connectionData) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('ssh_connect', {
                connection_id: this.connectionId
            });
        } else {
            setTimeout(() => this.connectToSSH(connectionData), 1000);
        }
    }
    
    handleTerminalInput(data) {
        if (!this.isConnected || !this.sshConnectionId) {
            this.term.writeln('\x1b[1;31mNot connected to SSH server\x1b[0m');
            return;
        }
        
        // Send input to SSH server via WebSocket
        this.socket.emit('ssh_data', {
            connection_id: this.sshConnectionId,
            data: data
        });
    }
    
    sendInput(data) {
        if (this.isConnected && this.sshConnectionId) {
            this.socket.emit('ssh_data', {
                connection_id: this.sshConnectionId,
                data: data
            });
        }
    }
    
    sendCommand(command) {
        if (command.trim()) {
            this.sendInput(command + '\n');
        }
    }
    
    updateStatus(text, type) {
        const statusElement = document.getElementById('connectionStatus');
        if (statusElement) {
            statusElement.textContent = text;
            statusElement.className = `badge bg-${type}`;
        }
    }
    
    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            this.updateStatus('Reconnecting...', 'warning');
            this.term.writeln(`\x1b[1;33mReconnecting (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...\x1b[0m`);
            
            if (this.sshConnectionId) {
                this.socket.emit('ssh_connect', {
                    connection_id: this.connectionId
                });
            }
        } else {
            this.term.writeln('\x1b[1;31mMax reconnection attempts reached\x1b[0m');
            this.updateStatus('Connection Failed', 'danger');
        }
    }
    
    setupEventListeners() {
        // Quick command input
        const quickCommand = document.getElementById('quickCommand');
        const sendCommandBtn = document.getElementById('sendCommand');
        const reconnectBtn = document.getElementById('reconnectBtn');
        
        if (quickCommand) {
            quickCommand.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendCommand(quickCommand.value);
                    quickCommand.value = '';
                }
            });
        }
        
        if (sendCommandBtn) {
            sendCommandBtn.addEventListener('click', () => {
                this.sendCommand(quickCommand.value);
                quickCommand.value = '';
                quickCommand.focus();
            });
        }
        
        if (reconnectBtn) {
            reconnectBtn.addEventListener('click', () => {
                this.reconnect();
            });
        }
        
        // Terminal settings
        const settingsBtn = document.getElementById('settingsBtn');
        const applySettingsBtn = document.getElementById('applySettings');
        const fontSizeSlider = document.getElementById('terminalFontSize');
        const themeSelect = document.getElementById('terminalTheme');
        
        if (fontSizeSlider) {
            fontSizeSlider.addEventListener('input', function() {
                document.getElementById('fontSizeValue').textContent = this.value + 'px';
            });
        }
        
        if (applySettingsBtn) {
            applySettingsBtn.addEventListener('click', () => {
                const fontSize = fontSizeSlider ? fontSizeSlider.value : 14;
                const theme = themeSelect ? themeSelect.value : 'dark';
                
                // Apply font size
                if (this.term) {
                    this.term.options.fontSize = parseInt(fontSize);
                }
                
                // Apply theme
                this.applyTheme(theme);
                
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
            });
        }
    }
    
    applyTheme(theme) {
        const container = document.getElementById('terminal-container');
        container.className = '';
        container.classList.add(`terminal-theme-${theme}`);
        
        switch(theme) {
            case 'dark':
                this.term.options.theme = {
                    background: '#000000',
                    foreground: '#00ff00',
                    cursor: '#00ff00'
                };
                break;
            case 'light':
                this.term.options.theme = {
                    background: '#ffffff',
                    foreground: '#000000',
                    cursor: '#000000'
                };
                break;
            case 'solarized':
                this.term.options.theme = {
                    background: '#002b36',
                    foreground: '#839496',
                    cursor: '#839496'
                };
                break;
            case 'matrix':
                this.term.options.theme = {
                    background: '#000000',
                    foreground: '#00ff00',
                    cursor: '#00ff00'
                };
                break;
        }
    }
    
    cleanup() {
        if (this.socket) {
            this.socket.disconnect();
        }
        if (this.term) {
            this.term.dispose();
        }
    }
}

// Initialize terminal when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.terminal = new WebSSHTerminal();
    
    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
        if (window.terminal) {
            window.terminal.cleanup();
        }
    });
    
    // Handle Ctrl+C for interrupt
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'c' && window.terminal && window.terminal.isConnected) {
            window.terminal.sendInput('\x03'); // Send Ctrl+C
            e.preventDefault();
        }
        
        if (e.ctrlKey && e.key === 'd' && window.terminal && window.terminal.isConnected) {
            window.terminal.sendInput('\x04'); // Send Ctrl+D
            e.preventDefault();
        }
    });
});
