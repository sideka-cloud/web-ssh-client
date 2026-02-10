document.addEventListener('DOMContentLoaded', function() {
    // Password validation
    const newPassword = document.getElementById('new_password');
    const confirmPassword = document.getElementById('confirm_password');
    const passwordForm = document.getElementById('passwordForm');
    
    function validatePasswords() {
        if (newPassword.value !== confirmPassword.value) {
            confirmPassword.setCustomValidity('Passwords do not match');
            confirmPassword.classList.add('is-invalid');
            return false;
        } else {
            confirmPassword.setCustomValidity('');
            confirmPassword.classList.remove('is-invalid');
            return true;
        }
    }
    
    newPassword.addEventListener('input', validatePasswords);
    confirmPassword.addEventListener('input', validatePasswords);
    
    // Form submission validation
    passwordForm.addEventListener('submit', function(e) {
        if (!validatePasswords()) {
            e.preventDefault();
            alert('New passwords do not match. Please check and try again.');
        }
    });
    
    // Toggle password visibility function
    function setupPasswordToggle(buttonId, inputId) {
        const toggleButton = document.getElementById(buttonId);
        const passwordInput = document.getElementById(inputId);
        
        if (toggleButton && passwordInput) {
            toggleButton.addEventListener('click', function() {
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                
                // Toggle icon
                const icon = this.querySelector('i');
                if (type === 'password') {
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                    this.classList.remove('active');
                } else {
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                    this.classList.add('active');
                }
            });
        }
    }
    
    // Setup toggle for each password field
    setupPasswordToggle('toggleCurrentPassword', 'current_password');
    setupPasswordToggle('toggleNewPassword', 'new_password');
    setupPasswordToggle('toggleConfirmPassword', 'confirm_password');
    
    // Clear password fields
    const clearButton = document.getElementById('clearPasswordFields');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            document.getElementById('current_password').value = '';
            document.getElementById('new_password').value = '';
            document.getElementById('confirm_password').value = '';
            confirmPassword.classList.remove('is-invalid');
        });
    }
    
    // Real-time password strength indicator (optional enhancement)
    newPassword.addEventListener('input', function() {
        const strengthIndicator = document.createElement('div');
        strengthIndicator.className = 'password-strength mt-2';
        
        const password = this.value;
        let strength = 0;
        
        // Check password strength
        if (password.length >= 10) strength++;
        if (/[A-Z]/.test(password)) strength++;
        if (/[a-z]/.test(password)) strength++;
        if (/[0-9]/.test(password)) strength++;
        if (/[^A-Za-z0-9]/.test(password)) strength++;
        
        // Update or create strength indicator
        let existingIndicator = this.parentElement.parentElement.querySelector('.password-strength');
        if (!existingIndicator) {
            existingIndicator = strengthIndicator;
            this.parentElement.parentElement.appendChild(existingIndicator);
        }
        
        const strengthText = ['Very Weak', 'Weak', 'Fair', 'Good', 'Strong', 'Very Strong'][strength];
        const strengthClass = ['text-danger', 'text-danger', 'text-warning', 'text-info', 'text-success', 'text-success'][strength];
        
        existingIndicator.innerHTML = `<small class="${strengthClass}"><i class="fas fa-shield-alt me-1"></i> Strength: ${strengthText}</small>`;
    });
});