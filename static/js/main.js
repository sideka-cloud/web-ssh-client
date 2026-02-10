// Main JavaScript for Web SSH Client

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.classList.contains('show')) {
                bootstrap.Alert.getInstance(alert).close();
            }
        }, 5000);
    });
    
    // Confirm before leaving unsaved forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        let formChanged = false;
        
        form.addEventListener('change', () => {
            formChanged = true;
        });
        
        form.addEventListener('submit', () => {
            formChanged = false;
        });
        
        window.addEventListener('beforeunload', (e) => {
            if (formChanged) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });
    });
    
    // Password strength checker
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        input.addEventListener('input', function() {
            const password = this.value;
            const strengthText = this.nextElementSibling;
            
            if (strengthText && strengthText.classList.contains('password-strength')) {
                let strength = 'Weak';
                let color = 'danger';
                
                if (password.length >= 12 && /[A-Z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)) {
                    strength = 'Very Strong';
                    color = 'success';
                } else if (password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password)) {
                    strength = 'Strong';
                    color = 'success';
                } else if (password.length >= 6) {
                    strength = 'Medium';
                    color = 'warning';
                }
                
                strengthText.innerHTML = `Password strength: <span class="text-${color}">${strength}</span>`;
            }
        });
    });
    
    // Copy to clipboard functionality
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const target = document.querySelector(targetId);
            
            if (target) {
                const text = target.value || target.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fas fa-check"></i> Copied!';
                    this.classList.add('btn-success');
                    
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove('btn-success');
                    }, 2000);
                });
            }
        });
    });
    
    // Connection test helper
    window.testSSHConnection = function(formData) {
        return fetch('/test_connection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        }).then(response => response.json());
    };
    
    // Initialize Socket.IO connection
    if (typeof io !== 'undefined') {
        window.socket = io();
        
        socket.on('connect', () => {
            console.log('Connected to server via WebSocket');
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
        });
    }
    
    // Prevent form resubmission on page refresh
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }
});
