// Dynamic sidebar behavior
document.addEventListener('DOMContentLoaded', function() {
    const mainContent = document.querySelector('.main-content-responsive');
    const sidebar = document.querySelector('.sidebar');
    
    // Add dynamic class based on authentication and page
    if (sidebar && mainContent) {
        mainContent.classList.add('with-sidebar');
    }
    
    // Email validation for Gmail
    const emailInputs = document.querySelectorAll('input[type="email"]');
    emailInputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (this.value && !this.value.endsWith('@gmail.com')) {
                this.setCustomValidity('Please use a Gmail address');
                this.reportValidity();
            } else {
                this.setCustomValidity('');
            }
        });
    });
    
    // Auto-fill username from email
    const emailField = document.getElementById('email');
    const usernameField = document.getElementById('username');
    
    if (emailField && usernameField) {
        emailField.addEventListener('input', function() {
            if (this.value.includes('@')) {
                const prefix = this.value.split('@')[0];
                if (!usernameField.value) {
                    usernameField.placeholder = `Suggested: ${prefix}`;
                }
            }
        });
    }
});
