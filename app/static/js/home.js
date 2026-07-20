// ── Scroll Animations ────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    // Animate feature cards
    document.querySelectorAll('.feature-card, .step, .testimonial-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

    // Animate section headers
    document.querySelectorAll('.section-header').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.8s ease, transform 0.8s ease';
        observer.observe(el);
    });
});

// ── Smooth Scroll for Nav Links ─────────────────────
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ── Navbar Shadow on Scroll ─────────────────────────
let nav = document.querySelector('nav');
window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
        nav.style.boxShadow = '0 4px 24px rgba(0,0,0,0.12)';
        nav.style.background = 'rgba(255,255,255,0.95)';
    } else {
        nav.style.boxShadow = '0 2px 16px rgba(0,0,0,0.07)';
        nav.style.background = 'rgba(255,255,255,0.82)';
    }
});

// ── Counter Animation for Stats ─────────────────────
function animateCounters() {
    const stats = document.querySelectorAll('.stat-number');
    stats.forEach(stat => {
        const text = stat.textContent;
        const num = parseInt(text.replace(/[^0-9]/g, ''));
        if (!num) return;

        let current = 0;
        const increment = Math.ceil(num / 60);
        const duration = 2000;
        const stepTime = Math.floor(duration / 60);

        const counter = setInterval(() => {
            current += increment;
            if (current >= num) {
                current = num;
                clearInterval(counter);
            }
            // Preserve suffix like K, +
            if (text.includes('K')) {
                stat.textContent = current + 'K+';
            } else if (text.includes('★')) {
                stat.textContent = current / 10 + '★';
            } else if (text.includes('+')) {
                stat.textContent = current + '+';
            } else {
                stat.textContent = current;
            }
        }, stepTime);
    });
}

// Trigger counter animation when hero stats are visible
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateCounters();
            statsObserver.unobserve(entry.target);
        }
    });
});

document.querySelectorAll('.hero-stats').forEach(el => {
    statsObserver.observe(el);
});

// ── Parallax Effect on Hero Visual ──────────────────
document.querySelector('.hero-visual')?.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.floating-card');
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    cards.forEach((card, i) => {
        const speed = 10 + i * 5;
        const moveX = x * speed;
        const moveY = y * speed;
        card.style.transform = `translate(${moveX}px, ${moveY}px)`;
    });
});

// ── Floating Orbs Parallax ──────────────────────────
document.addEventListener('mousemove', (e) => {
    const orbs = document.querySelectorAll('.floating-orb');
    const x = (e.clientX / window.innerWidth - 0.5) * 20;
    const y = (e.clientY / window.innerHeight - 0.5) * 20;

    orbs.forEach((orb, i) => {
        const speed = 15 + i * 5;
        orb.style.transform = `translate(${x * speed * 0.1}px, ${y * speed * 0.1}px)`;
    });
});

// ── Console Greeting ─────────────────────────────────
console.log('%c LecFlow ', 'background: #F97316; color: white; font-size: 20px; font-weight: bold; padding: 8px 16px; border-radius: 4px;');
console.log('%c Find. Learn. Flow. ', 'color: #F97316; font-size: 14px; font-weight: 500;');
console.log('%c Built for IIT Madras BS students ❤️', 'color: #6B7280; font-size: 12px;');