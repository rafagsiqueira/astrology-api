// Realistic user reviews data
const reviews = [
    {
        name: "Sarah M.",
        location: "San Francisco, CA",
        rating: 5,
        text: "Cosmic Guru has completely changed how I understand myself! The birth chart analysis was incredibly detailed and accurate. The AI chat feature feels like having a personal cosmicloger available 24/7.",
        initial: "S"
    },
    {
        name: "Michael R.",
        location: "Austin, TX",
        rating: 5,
        text: "I've tried many astrology apps, but nothing comes close to this level of personalization. The relationship compatibility feature helped me understand my partner better. Highly recommend!",
        initial: "M"
    },
    {
        name: "Luna P.",
        location: "Portland, OR",
        rating: 5,
        text: "As someone who's studied astrology for years, I'm impressed by the accuracy and depth of insights. The interface is beautiful and intuitive. This app respects the complexity of astrological wisdom.",
        initial: "L"
    },
    {
        name: "David K.",
        location: "New York, NY",
        rating: 4,
        text: "Never thought I'd be into astrology, but my friend convinced me to try this app. The personality insights were surprisingly on point, and I love how it explains everything in simple terms.",
        initial: "D"
    },
    {
        name: "Emma J.",
        location: "Seattle, WA",
        rating: 5,
        text: "The daily guidance feature is my favorite part of my morning routine. It's like having cosmic wisdom delivered personally to me. The relationship analysis with my boyfriend was spot on!",
        initial: "E"
    },
    {
        name: "Carlos V.",
        location: "Miami, FL",
        rating: 5,
        text: "Increíble! This app helped me understand why I connect so well with certain people. The birth chart visualization is stunning and the AI explanations are clear and insightful.",
        initial: "C"
    },
    {
        name: "Zoe T.",
        location: "Denver, CO",
        rating: 4,
        text: "Love how this app combines ancient wisdom with modern technology. The transit tracking helps me plan important decisions. It's become an essential part of my spiritual practice.",
        initial: "Z"
    },
    {
        name: "James H.",
        location: "Chicago, IL",
        rating: 5,
        text: "I was skeptical at first, but the accuracy of the personality analysis won me over. The app is beautifully designed and the chat feature provides thoughtful, personalized guidance.",
        initial: "J"
    },
    {
        name: "Aria S.",
        location: "Los Angeles, CA",
        rating: 5,
        text: "This app is a game-changer for anyone interested in astrology. The depth of information combined with the user-friendly interface makes it perfect for both beginners and experts.",
        initial: "A"
    },
    {
        name: "Ryan M.",
        location: "Phoenix, AZ",
        rating: 4,
        text: "Great for understanding myself and my relationships better. The compatibility feature with friends and family has given me so many 'aha!' moments. Customer support is also excellent.",
        initial: "R"
    }
];

// App store links (replace with actual URLs when available)
const APP_STORE_LINKS = {
    ios: 'https://apps.apple.com/app/cosmic-guru', // Replace with actual App Store URL
    android: 'https://play.google.com/store/apps/details?id=com.cosmicguru.app' // Replace with actual Play Store URL
};

// DOM elements
let reviewCarousel;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeReviews();
    setupDownloadButtons();
    setupMobileOptimizations();
    setupImageLoading();
});

// Initialize reviews with horizontal scroll
function initializeReviews() {
    reviewCarousel = document.getElementById('reviewCarousel');
    
    // Create review cards
    reviews.forEach((review, index) => {
        const reviewCard = createReviewCard(review, index);
        reviewCarousel.appendChild(reviewCard);
    });
}

// Create individual review card
function createReviewCard(review, index) {
    const card = document.createElement('div');
    card.className = 'review-card';
    
    // Generate star rating
    const stars = '★'.repeat(review.rating) + '☆'.repeat(5 - review.rating);
    
    card.innerHTML = `
        <div class="review-stars">${stars}</div>
        <div class="review-text">"${review.text}"</div>
        <div class="review-author">
            <div class="review-avatar">${review.initial}</div>
            <div class="review-details">
                <h4>${review.name}</h4>
                <p>${review.location}</p>
            </div>
        </div>
    `;
    
    return card;
}

// Setup download button functionality
function setupDownloadButtons() {
    const downloadButtons = document.querySelectorAll('.download-btn');
    
    downloadButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Determine which store based on button ID or user agent
            const isIOS = button.id.includes('app-store') || /iPad|iPhone|iPod/.test(navigator.userAgent);
            const isAndroid = button.id.includes('google-play') || /Android/.test(navigator.userAgent);
            
            // Add loading state
            const originalText = button.innerHTML;
            button.innerHTML = '<div class="loading"></div> Opening...';
            button.style.pointerEvents = 'none';
            
            // Simulate app store redirect (replace with actual URLs)
            setTimeout(() => {
                if (isIOS) {
                    window.open(APP_STORE_LINKS.ios, '_blank');
                } else if (isAndroid) {
                    window.open(APP_STORE_LINKS.android, '_blank');
                } else {
                    // Default to showing both options or detect platform
                    showStoreOptions();
                }
                
                // Reset button
                button.innerHTML = originalText;
                button.style.pointerEvents = 'auto';
            }, 1000);
        });
    });
}

// Show store options for desktop users
function showStoreOptions() {
    alert('Please visit the App Store (iOS) or Google Play Store (Android) to download Cosmic Guru on your mobile device.');
}

// Setup mobile-specific optimizations
function setupMobileOptimizations() {
    // Optimize touch interactions
    document.body.style.touchAction = 'manipulation';
    
    // Add viewport height fix for mobile browsers
    const setVH = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    };
    
    setVH();
    window.addEventListener('resize', setVH);
    window.addEventListener('orientationchange', setVH);
    
    // Optimize scrolling performance
    const carousels = document.querySelectorAll('.screenshot-carousel, .review-carousel');
    carousels.forEach(carousel => {
        carousel.style.scrollBehavior = 'smooth';
        carousel.style.overflowX = 'auto';
        carousel.style.WebkitOverflowScrolling = 'touch'; // iOS smooth scrolling
    });
}


// Add smooth scroll behavior for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
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

// Performance optimization: Lazy load heavy content
function setupLazyLoading() {
    const observerOptions = {
        root: null,
        rootMargin: '50px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('loaded');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe sections for lazy loading animations
    document.querySelectorAll('section').forEach(section => {
        observer.observe(section);
    });
}

// Setup image loading with fade-in effect
function setupImageLoading() {
    const images = document.querySelectorAll('.screenshot-image img');
    
    images.forEach(img => {
        const container = img.parentElement;
        
        if (img.complete && img.naturalHeight !== 0) {
            // Image already loaded
            img.classList.add('loaded');
            container.classList.add('loaded');
        } else {
            // Image not loaded yet
            img.addEventListener('load', function() {
                img.classList.add('loaded');
                container.classList.add('loaded');
            });
            
            img.addEventListener('error', function() {
                // Handle image load error
                console.warn('Failed to load screenshot:', img.src);
                container.classList.add('loaded');
                img.style.opacity = '0.5';
                img.alt = 'Screenshot not available';
            });
        }
    });
}

// Initialize lazy loading when DOM is ready
document.addEventListener('DOMContentLoaded', setupLazyLoading);

// Add CSS classes for loaded content
const style = document.createElement('style');
style.textContent = `
    section {
        opacity: 0;
        transform: translateY(30px);
        transition: opacity 0.6s ease, transform 0.6s ease;
    }
    
    section.loaded {
        opacity: 1;
        transform: translateY(0);
    }
    
    .hero {
        opacity: 1;
        transform: translateY(0);
    }
`;
document.head.appendChild(style);

// Analytics (placeholder - replace with actual analytics)
function trackEvent(eventName, properties) {
    // Replace with actual analytics implementation
    console.log('Analytics Event:', eventName, properties);
    
    // Example: Google Analytics 4
    if (typeof gtag !== 'undefined') {
        gtag('event', eventName, properties);
    }
}

// Track download button clicks
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('download-btn')) {
        trackEvent('download_button_click', {
            button_location: e.target.id || 'unknown',
            platform: e.target.id.includes('app-store') ? 'ios' : 'android'
        });
    }
});

// Track scroll depth for engagement
let maxScrollDepth = 0;
window.addEventListener('scroll', () => {
    const scrollDepth = Math.round((window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100);
    if (scrollDepth > maxScrollDepth) {
        maxScrollDepth = scrollDepth;
        
        // Track milestone scroll depths
        if ([25, 50, 75, 100].includes(scrollDepth)) {
            trackEvent('scroll_depth', {
                depth_percent: scrollDepth
            });
        }
    }
});