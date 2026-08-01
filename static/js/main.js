/* =========================================================
   AI Sleep Coach — Main JavaScript
   ========================================================= */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-hide flash messages setelah 5 detik
    const flashMessages = document.querySelectorAll('.flash');
    if (flashMessages.length > 0) {
        setTimeout(() => {
            flashMessages.forEach(msg => {
                msg.style.opacity = '0';
                msg.style.transform = 'translateX(100%)';
                msg.style.transition = 'all 0.4s ease';
                setTimeout(() => msg.remove(), 400);
            });
        }, 5000);
    }

    // 2. Smooth scrolling untuk anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                e.preventDefault();
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // 3. Efek navbar blur saat scroll
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 10) {
                navbar.style.background = 'rgba(8,12,24,0.95)';
                navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.4)';
            } else {
                navbar.style.background = 'rgba(8,12,24,0.85)';
                navbar.style.boxShadow = 'none';
            }
        });
    }
    // Force dark mode & remove any custom theme overrides
    document.documentElement.removeAttribute('data-theme');
    localStorage.removeItem('theme');
});
