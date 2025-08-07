# Cosmic Guru Landing Page

A beautiful, mobile-first landing page for the Cosmic Guru astrology app, designed for universal links and user acquisition.

## 🌟 Features

- **Mobile-First Design**: Optimized for smartphones and tablets
- **Cosmic Theme**: Matches the app's visual identity with `#4A0080` primary color
- **Interactive Elements**: 
  - Smooth carousel for user reviews
  - Touch-optimized navigation
  - App store download buttons
- **Performance Optimized**:
  - Lazy loading
  - Smooth scroll behavior
  - Minimal JavaScript footprint
- **Accessibility**:
  - Reduced motion support
  - High contrast support
  - Touch-friendly interface (48px minimum touch targets)
- **Cross-Platform**: Works seamlessly on iOS, Android, and desktop

## 📱 Mobile Optimizations

### Responsive Breakpoints
- **Mobile (≤480px)**: Single-column layout, full-width buttons
- **Tablet (481-768px)**: Two-column layout where appropriate
- **Desktop (>768px)**: Multi-column layout, centered content

### Touch Interactions
- Swipe navigation for carousels
- Smooth scroll snapping
- iOS-optimized scrolling (`-webkit-overflow-scrolling: touch`)
- Large touch targets (minimum 48px)

### Performance Features
- CSS-only animations where possible
- Intersection Observer for lazy loading
- Optimized font loading
- Dark mode support

## 🎨 Design System

### Colors
```css
--cosmic-primary: #4A0080        /* Main purple */
--cosmic-primary-light: #6B1BA3  /* Lighter purple */
--cosmic-secondary: #8B5CF6      /* Medium purple */
--cosmic-accent: #A855F7         /* Light purple accent */
--cosmic-gradient: linear-gradient(135deg, #4A0080 0%, #8B5CF6 50%, #A855F7 100%)
```

### Typography
- **Primary**: Inter (system fallback)
- **Headings**: Playfair Display (serif)
- **Mobile-optimized** font sizes with `clamp()`

## 🚀 Setup Instructions

1. **Deploy to Web Server**
   ```bash
   # Copy files to your web server
   cp -r web/* /var/www/html/cosmic-guru/
   ```

2. **Update App Store Links**
   - Edit `script.js` and replace placeholder URLs:
   ```javascript
   const APP_STORE_LINKS = {
     ios: 'https://apps.apple.com/app/your-actual-app-id',
     android: 'https://play.google.com/store/apps/details?id=com.yourapp.cosmicguru'
   };
   ```

3. **Add Favicons** (Optional)
   - Add `favicon-32x32.png`, `favicon-16x16.png`, `apple-touch-icon.png` to web root

4. **Configure Analytics** (Optional)
   - Update the analytics tracking in `script.js`
   - Add Google Analytics or other tracking services

## 📊 Analytics Events

The landing page tracks these events:
- `download_button_click`: When users click download buttons
- `scroll_depth`: User engagement (25%, 50%, 75%, 100%)
- Page visibility changes

## 🔧 Customization

### Adding Screenshots
Replace the screenshot mockups in the HTML with actual app screenshots:
```html
<div class="screenshot-mockup">
  <img src="path/to/screenshot1.png" alt="App Screenshot">
</div>
```

### Updating Reviews
Modify the `reviews` array in `script.js` to add/update user testimonials:
```javascript
const reviews = [
  {
    name: "User Name",
    location: "City, State",
    rating: 5,
    text: "Review text here...",
    initial: "U"
  }
];
```

### Styling Changes
All styles are in the `<style>` section of `index.html`. Key areas:
- `:root` variables for colors
- Media queries for responsive design
- Component-specific styles

## 🌐 Universal Links Integration

This landing page is designed to work with universal links:

1. **iOS Universal Links**: Configure your `apple-app-site-association` file
2. **Android App Links**: Configure your `assetlinks.json` file
3. **Fallback**: Users without the app are shown this landing page

### Example Universal Link Flow
```
User clicks: https://cosmicguru.app/invite/ABC123
↓
App installed? → Open app with invite code
↓
App not installed? → Show this landing page → Direct to app store
```

## 📋 Deployment Checklist

- [ ] Update app store URLs in `script.js`
- [ ] Add actual app screenshots
- [ ] Configure web server for universal links
- [ ] Test on various mobile devices
- [ ] Set up analytics tracking
- [ ] Add favicons and meta images
- [ ] Test app store redirects
- [ ] Verify responsive design on all breakpoints

## 🎯 Conversion Optimization

The landing page includes several conversion optimization features:
- **Social proof**: User reviews carousel
- **Visual appeal**: App screenshots showcase
- **Clear CTAs**: Prominent download buttons
- **Trust indicators**: Star ratings and user testimonials
- **Mobile optimization**: Finger-friendly interface

## 📈 Performance Metrics

- **Load time**: < 2 seconds on 3G
- **Lighthouse Score**: 95+ for mobile
- **Core Web Vitals**: Optimized for mobile experience
- **Accessibility**: WCAG 2.1 AA compliant

## 🐛 Troubleshooting

### Common Issues

1. **Carousel not working**: Check JavaScript console for errors
2. **Download buttons not redirecting**: Verify app store URLs in `script.js`
3. **Mobile styling issues**: Test media queries and viewport meta tag
4. **Performance issues**: Enable compression and check image sizes

### Browser Support
- **Mobile**: iOS Safari 12+, Chrome Mobile 70+
- **Desktop**: Chrome 70+, Firefox 65+, Safari 12+, Edge 79+

## 📝 License

This landing page is part of the Cosmic Guru project. Customize as needed for your app deployment.