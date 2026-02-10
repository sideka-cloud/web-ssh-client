document.addEventListener('DOMContentLoaded', function() {
    // Toggle password visibility
    const toggleBtn = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    
    toggleBtn.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        toggleBtn.innerHTML = type === 'password' ? '<i class="fas fa-eye"></i>' : '<i class="fas fa-eye-slash"></i>';
    });
    
    // Toggle auth methods
    const authMethodRadios = document.querySelectorAll('input[name="auth_method"]');
    const passwordAuth = document.getElementById('password_auth');
    const keyAuth = document.getElementById('key_auth');
    
    authMethodRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'password') {
                passwordAuth.classList.add('active');
                keyAuth.classList.remove('active');
                passwordInput.required = true;
                document.getElementById('private_key').required = false;
            } else {
                passwordAuth.classList.remove('active');
                keyAuth.classList.add('active');
                passwordInput.required = false;
                document.getElementById('private_key').required = true;
            }
        });
    });
    
    // Test connection
    const testBtn = document.getElementById('testConnectionBtn');
    const testResult = document.getElementById('testResult');
    
    testBtn.addEventListener('click', function() {
        const formData = {
            hostname: document.getElementById('hostname').value,
            port: document.getElementById('port').value || 22,
            username: document.getElementById('username').value,
            password: document.getElementById('password').value,
            private_key: document.getElementById('private_key').value
        };
        
        if (!formData.hostname || !formData.username) {
            showTestResult('Please fill in required fields', 'danger');
            return;
        }
        
        testBtn.disabled = true;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        showTestResult('Testing connection...', 'info');
        
        fetch('/test_connection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showTestResult('✓ Connection successful!', 'success');
            } else {
                showTestResult('✗ Connection failed: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            showTestResult('✗ Error: ' + error.message, 'danger');
        })
        .finally(() => {
            testBtn.disabled = false;
            testBtn.innerHTML = '<i class="fas fa-plug"></i> Test Connection';
        });
    });
    
    function showTestResult(message, type) {
        testResult.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    }
});