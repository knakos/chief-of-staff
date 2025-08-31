# URL Formatter Utilities

This directory contains utilities for consistently formatting URLs across the Chief of Staff application.

## Files

- `url-formatter.js` - Core URL formatting utilities
- `README.md` - This documentation file

## Usage

The URL formatter is automatically loaded in the main application and available globally.

### React Components

Use these React components for automatic URL formatting:

```jsx
// Format text containing URLs automatically
<FormattedText text="Check out https://example.com for more info" />
// Renders: Check out [here] for more info (with clickable link)

// Format text with custom link text  
<FormattedText text="Visit https://github.com" linkText="GitHub" />
// Renders: Visit [GitHub] (with clickable link)

// Single URL link component
<UrlLink url="https://example.com">Click here</UrlLink>
// Renders: Click here (as clickable link)

<UrlLink url="https://example.com" />
// Renders: [here] (as clickable link)
```

### JavaScript Functions

Direct JavaScript usage (available as `window.UrlFormatter`):

```javascript
// Format URLs in text
const formatted = await UrlFormatter.formatUrlsInText(
  "Visit https://example.com for details", 
  "here"
);

// Format URLs with custom text for different domains
const customFormatted = await UrlFormatter.formatUrlsWithCustomText(
  "Check https://github.com and https://stackoverflow.com", 
  {
    "github.com": "GitHub",
    "stackoverflow.com": "Stack Overflow"
  }
);

// Apply formatting to DOM element
await UrlFormatter.formatUrlsInElement(document.getElementById('content'));

// Check if text contains URLs
if (UrlFormatter.containsUrls(someText)) {
  // Handle text with URLs
}

// Extract all URLs from text
const urls = UrlFormatter.extractUrls("Text with https://example.com");
```

## Styling

URL styling is controlled by the `design/settings.json` file:

```json
{
  "theme": {
    "colors": {
      "link": {
        "primary": "#1d4ed8",
        "hover": "#2563eb", 
        "visited": "#7c3aed",
        "underlineColor": "#1d4ed8"
      }
    }
  }
}
```

These colors are automatically applied as CSS custom properties:
- `--link-primary` - Default link color
- `--link-hover` - Hover state color  
- `--link-visited` - Visited link color
- `--link-underline` - Underline color

## Examples

### Chat Messages
```jsx
// AI messages automatically format URLs
const aiMessage = "I found this helpful resource: https://docs.example.com/api";
<FormattedText text={aiMessage} />
```

### Email Content
```jsx
// Format URLs in email previews
<FormattedText 
  text={email.body_preview} 
  linkText="view" 
  className="email-preview" 
/>
```

### Documentation
```jsx
// Custom link text for different services
<FormattedText 
  text="Check the GitHub repo: https://github.com/user/repo and Stack Overflow: https://stackoverflow.com/questions/123"
  linkText="documentation"
/>
```

## Implementation Notes

- URLs are automatically detected using regex pattern
- Links open in new tabs with `target="_blank"` and `rel="noopener noreferrer"`
- Hover effects and transitions are applied automatically
- All styling comes from the settings file for consistency
- Components gracefully fallback if utilities fail to load
- Supports both HTTP and HTTPS URLs
- Handles complex URLs with query parameters and fragments

## Browser Compatibility

Works in all modern browsers supporting:
- ES6 async/await
- CSS custom properties
- React 18+