const socket = io();

// Listen for session count updates
socket.on('session_count_update', function(data) {
    console.log('📡 Session count update received:', data);
    
    const activeCountElement = document.querySelector('.stats-card.bg-info .card-value');
    if (activeCountElement && data.active_count !== undefined) {
        // Update the counter with animation
        activeCountElement.textContent = data.active_count;
        
        // Add visual feedback
        activeCountElement.style.transition = 'all 0.3s ease';
        activeCountElement.style.transform = 'scale(1.3)';
        activeCountElement.style.color = '#ffeb3b';
        
        setTimeout(() => {
            activeCountElement.style.transform = 'scale(1)';
            activeCountElement.style.color = '';
        }, 300);
        
        // Update system status active users
        const activeUsersBadge = document.querySelector('.system-status .status-item:last-child .status-badge');
        if (activeUsersBadge) {
            activeUsersBadge.textContent = data.active_count;
        }
    }
});

socket.on('session_cleanup', function(data) {
    console.log('🧹 Session cleanup:', data);
    // Optional: Show notification about session cleanup
});

// Function to fetch active session count via AJAX
function fetchActiveSessionCount() {
    fetch('/api/active_sessions')
        .then(response => response.json())
        .then(data => {
            const activeCountElement = document.querySelector('.stats-card.bg-info .card-value');
            if (activeCountElement) {
                activeCountElement.textContent = data.active_count;
            }
        })
        .catch(error => console.error('Error fetching session count:', error));
}

// Fetch session count on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initial fetch
    fetchActiveSessionCount();
    
    // Set up periodic refresh (every 30 seconds)
    setInterval(fetchActiveSessionCount, 30000);

    // Auto-refresh dashboard every 60 seconds
    let refreshTimer = setTimeout(() => {
        window.location.reload();
    }, 60000);

    // Reset timer on user activity
    document.addEventListener('click', function() {
        clearTimeout(refreshTimer);
        refreshTimer = setTimeout(() => {
            window.location.reload();
        }, 60000);
    });

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Add animation to cards on load
    const cards = document.querySelectorAll('.stats-card, .content-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';

        setTimeout(() => {
            card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });

    // Enhanced hover effects for table rows
    const tableRows = document.querySelectorAll('.connections-table tbody tr');
    tableRows.forEach((row, index) => {
        row.style.setProperty('--row-index', index);
        
        // Add ripple effect on click
        row.addEventListener('click', function(e) {
            if (e.target.tagName === 'A' || e.target.closest('a')) {
                return; // Don't trigger ripple for link clicks
            }
            
            const ripple = document.createElement('div');
            ripple.style.position = 'absolute';
            ripple.style.borderRadius = '50%';
            ripple.style.backgroundColor = 'rgba(102, 126, 234, 0.2)';
            ripple.style.transform = 'scale(0)';
            ripple.style.animation = 'ripple 0.6s linear';
            ripple.style.top = e.offsetY + 'px';
            ripple.style.left = e.offsetX + 'px';
            ripple.style.width = '100px';
            ripple.style.height = '100px';
            ripple.style.pointerEvents = 'none';
            
            this.style.position = 'relative';
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });

    // Add CSS for ripple animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // Parallax effect for stats cards on mouse move
    const statsCards = document.querySelectorAll('.stats-card');
    statsCards.forEach(card => {
        card.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateY = (x - centerX) / 25;
            const rotateX = (centerY - y) / 25;
            
            this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-8px)`;
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) translateY(-8px)';
        });
    });

    // Add pulse animation to active stats
    const activeCard = document.querySelector('.stats-card.bg-info');
    if (activeCard) {
        setInterval(() => {
            const activeCount = parseInt(activeCard.querySelector('.card-value').textContent);
            if (activeCount > 0) {
                activeCard.style.boxShadow = '0 12px 30px rgba(54, 209, 220, 0.5)';
                setTimeout(() => {
                    activeCard.style.boxShadow = '0 12px 30px rgba(0, 0, 0, 0.15)';
                }, 1000);
            }
        }, 3000);
    }
});