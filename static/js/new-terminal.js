let term = null;
let socket = null;
let fitAddon = null;
let webglAddon = null;
let currentSessionId = null;
let isConnected = false;
let outputPollingInterval = null;
let sessionStartTime = null;
let bytesSent = 0;
let bytesReceived = 0;

// Terminal themes
const themes = {
    dark: {
        background: '#000000',
        foreground: '#00ff00',
        cursor: '#00ff00',
        selection: 'rgba(0, 255, 0, 0.3)'
    },
    light: {
        background: '#ffffff',
        foreground: '#000000',
        cursor: '#000000',
        selection: 'rgba(0, 0, 0, 0.3)'
    },
    solarized: {
        background: '#002b36',
        foreground: '#839496',
        cursor: '#839496',
        selection: 'rgba(131, 148, 150, 0.3)'
    },
    matrix: {
        background: '#000000',
        foreground: '#00ff00',
        cursor: '#00ff00',
        selection: 'rgba(0, 255, 0, 0.3)'
    },
    ubuntu: {
        background: '#300a24',
        foreground: '#ffffff',
        cursor: '#ffffff',
        selection: 'rgba(255, 255, 255, 0.3)'
    }
};

// Initialize terminal
function initTerminal() {
    // Clear previous terminal if exists
    if (term) {
        term.dispose();
        if (window.terminalResizeObserver) {
            window.terminalResizeObserver.disconnect();
        }
    }

    // Set default values untuk input settings
    document.getElementById('fontSize').value = 14;
    document.getElementById('fontSizeValue').textContent = '14px';
    document.getElementById('terminalTheme').value = 'ubuntu';

    // Create new terminal dengan default
    term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: '"Cascadia Code", "Courier New", monospace',
        theme: themes.ubuntu,
        allowTransparency: false,
        convertEol: true,
        disableStdin: false,
        cursorStyle: 'block',
        allowProposedApi: true,
        scrollback: 10000,
        cols: 80,
        rows: 26
    });

    // Create addons
    fitAddon = new FitAddon.FitAddon();
    webglAddon = new WebglAddon.WebglAddon();

    // Load addons
    try {
        term.loadAddon(fitAddon);
        term.loadAddon(webglAddon);
        webglAddon.onContextLoss(() => {
            webglAddon.dispose();
        });
    } catch (e) {
        console.warn("WebGL not supported:", e);
    }

    // Open terminal
    const container = document.getElementById('terminal-container');
    term.open(container);

    // Fit to container dengan multiple attempts
    fitTerminalWithRetry();

    // Setup ResizeObserver untuk monitor perubahan ukuran
    setupResizeObserver();

    // Handle terminal input
    term.onData(data => {
        if (isConnected && socket && currentSessionId) {
            // Send input to persistent SSH session
            socket.emit('persistent_ssh_input', {
                session_id: currentSessionId,
                data: data
            });

            // Update bytes sent
            bytesSent += data.length;
            updateStats();
        }
    });

    // Handle terminal resize
    term.onResize(size => {
        if (isConnected && socket && currentSessionId) {
            socket.emit('resize_persistent_terminal', {
                session_id: currentSessionId,
                cols: size.cols,
                rows: size.rows
            });
        }
    });

    // Write welcome message
    term.writeln('\x1b[1;32m=== Web SSH Client ===\x1b[0m');
    term.writeln('\x1b[1;36mClick "Connect" to start SSH session\x1b[0m');
    term.writeln('\x1b[1;33m✓ Press Ctrl+C to interrupt | Ctrl+D to exit\x1b[0m');
    term.writeln('');
}

// Fungsi untuk fitting terminal dengan retry mechanism
function fitTerminalWithRetry(retryCount = 0, maxRetries = 10) {
    if (retryCount >= maxRetries) {
        console.error('Failed to fit terminal after', maxRetries, 'attempts');
        return;
    }

    try {
        // Force a reflow
        const container = document.getElementById('terminal-container');
        if (container) {
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            if (width > 0 && height > 0) {
                fitAddon.fit();
                
                const dimensions = fitAddon.proposeDimensions();
                if (dimensions && dimensions.cols > 0 && dimensions.rows > 0) {
                    console.log('Terminal fitted to:', dimensions.cols, 'cols x', dimensions.rows, 'rows');
                    
                    // Jika terkoneksi, kirim resize ke server
                    if (isConnected && socket && currentSessionId) {
                        socket.emit('resize_persistent_terminal', {
                            session_id: currentSessionId,
                            cols: dimensions.cols,
                            rows: dimensions.rows
                        });
                    }
                    
                    term.focus();
                    return; // Success
                }
            }
        }
        
        // Jika belum berhasil, coba lagi
        setTimeout(() => {
            fitTerminalWithRetry(retryCount + 1, maxRetries);
        }, 100);
    } catch (error) {
        console.error('Error fitting terminal:', error);
        setTimeout(() => {
            fitTerminalWithRetry(retryCount + 1, maxRetries);
        }, 100);
    }
}

// Setup ResizeObserver
function setupResizeObserver() {
    if (window.terminalResizeObserver) {
        window.terminalResizeObserver.disconnect();
    }
    
    const container = document.getElementById('terminal-container');
    
    window.terminalResizeObserver = new ResizeObserver(() => {
        clearTimeout(window.fitTimeout);
        window.fitTimeout = setTimeout(() => {
            fitTerminalWithRetry();
        }, 50);
    });
    
    if (container) {
        window.terminalResizeObserver.observe(container);
    }
}

// Initialize Socket.IO
function initSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('WebSocket connected');
        updateStatus('Ready to connect', 'disconnected');
    });

    socket.on('ssh_session_started', (data) => {
        console.log('Persistent SSH session started:', data);
        currentSessionId = data.session_id;
        isConnected = true;
        sessionStartTime = new Date();

        updateStatus('Connected to SSH', 'connected');
        term.clear();
        term.writeln('\x1b[1;32m✓ SSH session established\x1b[0m');
        term.writeln('\x1b[1;36mConnected to: ' + data.hostname + '\x1b[0m');
        term.writeln('');

        // Enable/disable buttons
        document.getElementById('connectBtn').disabled = true;
        document.getElementById('disconnectBtn').disabled = false;
        document.getElementById('reconnectBtn').disabled = false;

        // Start output polling
        startOutputPolling();

        // Start session timer
        startSessionTimer();

        // Focus terminal
        term.focus();
        
        // Resize terminal setelah koneksi
        setTimeout(() => fitTerminalWithRetry(), 100);
    });

    socket.on('ssh_output', (data) => {
        if (data.session_id === currentSessionId) {
            // Write output to terminal
            term.write(data.data);

            // Update bytes received
            bytesReceived += data.data.length;
            updateStats();

            // Update last activity
            updateLastActivity();
        }
    });

    socket.on('ssh_error', (data) => {
        term.writeln(`\x1b[1;31m✗ Error: ${data.message}\x1b[0m`);
        updateStatus('Connection error', 'disconnected');
        disconnectSSH();
    });

    socket.on('ssh_session_closed', (data) => {
        term.writeln('\x1b[1;33m✓ SSH session closed\x1b[0m');
        updateStatus('Disconnected', 'disconnected');
        disconnectSSH();
    });

    socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        updateStatus('Disconnected', 'disconnected');
        disconnectSSH();
    });
}

// Update status indicator
function updateStatus(text, status) {
    const statusElement = document.getElementById('connectionStatus');
    const indicator = statusElement.querySelector('.status-indicator');

    // Update classes
    indicator.className = 'status-indicator';
    indicator.classList.add(`status-${status}`);

    // Update text
    statusElement.querySelector('span:last-child').textContent = text;
}

// Connect to SSH
function connectSSH() {
    const connectionId = document.getElementById('connectionId').value;

    updateStatus('Connecting...', 'connecting');
    term.writeln('\x1b[1;33mConnecting to SSH server...\x1b[0m');

    socket.emit('start_persistent_ssh', {
        connection_id: connectionId
    });
}

// Disconnect from SSH
function disconnectSSH() {
    if (currentSessionId && socket) {
        socket.emit('close_persistent_ssh', {
            session_id: currentSessionId
        });
    }

    cleanupSession();
}

// Cleanup session
function cleanupSession() {
    isConnected = false;
    currentSessionId = null;

    // Stop polling
    if (outputPollingInterval) {
        clearInterval(outputPollingInterval);
        outputPollingInterval = null;
    }

    // Stop timer
    if (sessionTimerInterval) {
        clearInterval(sessionTimerInterval);
        sessionTimerInterval = null;
    }

    // Update UI
    document.getElementById('connectBtn').disabled = false;
    document.getElementById('disconnectBtn').disabled = true;
    document.getElementById('reconnectBtn').disabled = true;

    // Reset stats
    bytesSent = 0;
    bytesReceived = 0;
    updateStats();
    document.getElementById('sessionTimer').textContent = '00:00:00';
}

// Start output polling
function startOutputPolling() {
    if (outputPollingInterval) {
        clearInterval(outputPollingInterval);
    }

    outputPollingInterval = setInterval(() => {
        if (isConnected && socket && currentSessionId) {
            socket.emit('get_persistent_output', {
                session_id: currentSessionId
            });
        }
    }, 50);
}

// Session timer
let sessionTimerInterval = null;
function startSessionTimer() {
    if (sessionTimerInterval) {
        clearInterval(sessionTimerInterval);
    }

    sessionTimerInterval = setInterval(() => {
        if (sessionStartTime) {
            const elapsed = new Date() - sessionStartTime;
            const hours = Math.floor(elapsed / 3600000);
            const minutes = Math.floor((elapsed % 3600000) / 60000);
            const seconds = Math.floor((elapsed % 60000) / 1000);

            document.getElementById('sessionTimer').textContent =
                `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }, 1000);
}

// Update statistics
function updateStats() {
    document.getElementById('bytesSent').textContent = formatBytes(bytesSent);
    document.getElementById('bytesReceived').textContent = formatBytes(bytesReceived);
}

// Format bytes
function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// Update last activity
function updateLastActivity() {
    const now = new Date();
    document.getElementById('lastActivity').textContent =
        `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

// Fungsi untuk menjalankan command dari tombol
function executeQuickCommand(command) {
    if (!isConnected || !socket || !currentSessionId) {
        term.writeln('\x1b[1;31mNot connected to SSH server. Please connect first.\x1b[0m');
        return;
    }

    console.log('Executing quick command:', command);
    
    // Kirim command ke terminal dengan Enter (\r)
    const fullCommand = command + '\r';
    
    socket.emit('persistent_ssh_input', {
        session_id: currentSessionId,
        data: fullCommand
    });

    // Update bytes sent
    bytesSent += fullCommand.length;
    updateStats();
    
    // Focus kembali ke terminal
    term.focus();
}

// Apply terminal settings
function applySettings() {
    const fontSize = parseInt(document.getElementById('fontSize').value);
    const theme = document.getElementById('terminalTheme').value;
    const terminalType = document.getElementById('terminalType').value;
    const enableBell = document.getElementById('enableBell').checked;
    const enableBlink = document.getElementById('enableBlink').checked;

    // Apply font size
    term.options.fontSize = fontSize;
    document.getElementById('fontSizeValue').textContent = fontSize + 'px';

    // Apply theme
    term.options.theme = themes[theme];

    // Apply other options
    term.options.bellStyle = enableBell ? 'sound' : 'none';
    term.options.cursorBlink = enableBlink;

    // Resize terminal setelah perubahan settings
    setTimeout(() => fitTerminalWithRetry(), 50);

    // Send terminal type to server if connected
    if (isConnected && socket && currentSessionId) {
        console.log('Terminal type changed to:', terminalType);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing terminal...');
    
    // Tunggu agar DOM benar-benar siap
    setTimeout(() => {
        // Initialize terminal
        initTerminal();

        // Initialize WebSocket
        initSocket();

        // Setup event listeners
        setupEventListeners();
        
        console.log('Terminal initialized');
    }, 100);
});

// Setup semua event listeners
function setupEventListeners() {
    // Event listeners untuk koneksi
    document.getElementById('connectBtn').addEventListener('click', connectSSH);
    document.getElementById('disconnectBtn').addEventListener('click', disconnectSSH);
    document.getElementById('reconnectBtn').addEventListener('click', () => {
        disconnectSSH();
        setTimeout(connectSSH, 500);
    });

    // Terminal control buttons
    document.getElementById('clearBtn').addEventListener('click', () => term.clear());
    document.getElementById('copyBtn').addEventListener('click', () => {
        const selection = term.getSelection();
        if (selection) {
            navigator.clipboard.writeText(selection);
        }
    });
    document.getElementById('pasteBtn').addEventListener('click', () => {
        navigator.clipboard.readText().then(text => {
            term.paste(text);
        });
    });
    
    // Fullscreen button
    document.getElementById('fullscreenBtn').addEventListener('click', () => {
        const wrapper = document.querySelector('.terminal-wrapper');
        if (!document.fullscreenElement) {
            wrapper.requestFullscreen().catch(err => {
                console.error('Fullscreen error:', err);
            });
        } else {
            document.exitFullscreen();
        }
    });

    // Quick command buttons - DIPERBARUI
    document.querySelectorAll('.quick-cmd').forEach(btn => {
        btn.addEventListener('click', function() {
            const cmd = this.getAttribute('data-cmd');
            executeQuickCommand(cmd);
        });
    });

    // Settings
    document.getElementById('fontSize').addEventListener('input', function() {
        document.getElementById('fontSizeValue').textContent = this.value + 'px';
    });

    document.getElementById('applySettings').addEventListener('click', function() {
        applySettings();
        bootstrap.Modal.getInstance(document.getElementById('settingsModal')).hide();
    });

    // Handle special keys
    document.addEventListener('keydown', (e) => {
        // Focus terminal when any key is pressed (except in input fields)
        if (!['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
            term.focus();
        }

        // Handle Ctrl+C and Ctrl+D
        if (e.ctrlKey && isConnected) {
            if (e.key === 'c') {
                // Ctrl+C - interrupt
                socket.emit('persistent_ssh_input', {
                    session_id: currentSessionId,
                    data: '\x03'
                });
                e.preventDefault();
            } else if (e.key === 'd') {
                // Ctrl+D - exit/EOF
                socket.emit('persistent_ssh_input', {
                    session_id: currentSessionId,
                    data: '\x04'
                });
                e.preventDefault();
            } else if (e.key === 'l') {
                // Ctrl+L - clear screen
                term.clear();
                e.preventDefault();
            }
        }

        // Handle arrow keys
        if (e.key.startsWith('Arrow') && isConnected) {
            let sequence = '';
            switch(e.key) {
                case 'ArrowUp': sequence = '\x1b[A'; break;
                case 'ArrowDown': sequence = '\x1b[B'; break;
                case 'ArrowRight': sequence = '\x1b[C'; break;
                case 'ArrowLeft': sequence = '\x1b[D'; break;
            }

            if (sequence) {
                socket.emit('persistent_ssh_input', {
                    session_id: currentSessionId,
                    data: sequence
                });
                e.preventDefault();
            }
        }
    });

    // Handle window resize
    window.addEventListener('resize', () => {
        clearTimeout(window.resizeTimeout);
        window.resizeTimeout = setTimeout(() => {
            fitTerminalWithRetry();
        }, 150);
    });

    // Handle fullscreen change events
    document.addEventListener('fullscreenchange', () => {
        setTimeout(() => fitTerminalWithRetry(), 100);
    });
    document.addEventListener('webkitfullscreenchange', () => {
        setTimeout(() => fitTerminalWithRetry(), 100);
    });
    document.addEventListener('mozfullscreenchange', () => {
        setTimeout(() => fitTerminalWithRetry(), 100);
    });
    document.addEventListener('MSFullscreenChange', () => {
        setTimeout(() => fitTerminalWithRetry(), 100);
    });

    // Initial stats update
    updateStats();
    updateLastActivity();
}