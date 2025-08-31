// CSS Generator - Reads settings.json and generates CSS custom properties
function generateCSS(settings) {
  const { theme, layout, components } = settings;
  
  let css = `/* Auto-generated CSS from settings.json */\n\n:root {\n`;
  
  // Colors
  css += `  /* Background Colors */\n`;
  Object.entries(theme.colors.background).forEach(([key, value]) => {
    css += `  --bg-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}: ${value};\n`;
  });
  
  css += `\n  /* Surface Colors */\n`;
  Object.entries(theme.colors.surface).forEach(([key, value]) => {
    css += `  --surface-${key === 'default' ? 'base' : key}: ${value};\n`;
  });
  
  css += `\n  /* Text Colors */\n`;
  Object.entries(theme.colors.text).forEach(([key, value]) => {
    css += `  --text-${key}: ${value};\n`;
  });
  
  css += `\n  /* Border Colors */\n`;
  Object.entries(theme.colors.border).forEach(([key, value]) => {
    css += `  --border-${key === 'default' ? 'base' : key}: ${value};\n`;
  });
  
  css += `\n  /* Brand Colors */\n`;
  Object.entries(theme.colors.brand).forEach(([key, value]) => {
    css += `  --brand-${key}: ${value};\n`;
  });
  
  css += `\n  /* Status Colors */\n`;
  Object.entries(theme.colors.status).forEach(([key, value]) => {
    const kebabKey = key.replace(/([A-Z])/g, '-$1').toLowerCase();
    css += `  --${kebabKey}: ${value};\n`;
  });
  
  // Typography
  css += `\n  /* Typography */\n`;
  css += `  --font-family: ${theme.typography.fontFamily};\n`;
  css += `  --font-display: ${theme.typography.fontDisplay};\n`;
  css += `  --font-mono: ${theme.typography.fontMono};\n`;
  
  Object.entries(theme.typography.fontSize).forEach(([key, value]) => {
    css += `  --font-size-${key}: ${value};\n`;
  });
  
  Object.entries(theme.typography.fontWeight).forEach(([key, value]) => {
    css += `  --font-weight-${key}: ${value};\n`;
  });
  
  Object.entries(theme.typography.lineHeight).forEach(([key, value]) => {
    css += `  --line-height-${key}: ${value};\n`;
  });
  
  // Spacing
  css += `\n  /* Spacing */\n`;
  Object.entries(theme.spacing).forEach(([key, value]) => {
    css += `  --space-${key}: ${value};\n`;
  });
  
  // Border Radius
  css += `\n  /* Border Radius */\n`;
  Object.entries(theme.borderRadius).forEach(([key, value]) => {
    css += `  --radius-${key}: ${value};\n`;
  });
  
  // Shadows
  css += `\n  /* Shadows */\n`;
  Object.entries(theme.shadows).forEach(([key, value]) => {
    css += `  --shadow-${key}: ${value};\n`;
  });
  
  // Transitions
  css += `\n  /* Transitions */\n`;
  Object.entries(theme.transitions).forEach(([key, value]) => {
    css += `  --duration-${key === 'ease' ? 'ease' : `${key}`}: ${value};\n`;
  });
  
  // Layout
  css += `\n  /* Layout */\n`;
  css += `  --sidebar-width: ${layout.sidebar.width};\n`;
  css += `  --chatbox-width: ${layout.chatbox.width};\n`;
  css += `  --container-max: ${layout.container.maxWidth};\n`;
  
  css += `}\n\n`;
  
  // Base styles
  css += `/* Base Styles */\n`;
  css += `* {\n  box-sizing: border-box;\n}\n\n`;
  css += `html, body {\n  margin: 0;\n  padding: 0;\n  font-family: var(--font-family);\n  font-size: var(--font-size-base);\n  line-height: var(--line-height-base);\n  background: var(--bg-primary);\n  color: var(--text-primary);\n  font-weight: var(--font-weight-normal);\n}\n\n`;
  
  // Utility classes
  css += `/* Utility Classes */\n`;
  css += `.col { display: flex; flex-direction: column; }\n`;
  css += `.row { display: flex; flex-direction: row; align-items: center; }\n\n`;
  
  // Gap utilities
  ['2', '3', '4', '6'].forEach(size => {
    css += `.gap-${size} { gap: var(--space-${size}); }\n`;
  });
  css += `\n`;
  
  // Padding utilities
  ['2', '3', '4', '6'].forEach(size => {
    css += `.p-${size} { padding: var(--space-${size}); }\n`;
  });
  css += `\n`;
  
  // Margin utilities
  ['2', '3', '4', '6'].forEach(size => {
    css += `.mb-${size} { margin-bottom: var(--space-${size}); }\n`;
  });
  css += `\n`;
  
  // Text utilities
  css += `.text-sm { font-size: var(--font-size-sm); }\n`;
  css += `.text-lg { font-size: var(--font-size-lg); }\n`;
  css += `.text-xl { font-size: var(--font-size-xl); }\n`;
  css += `.text-2xl { font-size: var(--font-size-2xl); }\n\n`;
  css += `.font-medium { font-weight: var(--font-weight-medium); }\n`;
  css += `.font-semibold { font-weight: var(--font-weight-semibold); }\n`;
  css += `.font-bold { font-weight: var(--font-weight-bold); }\n\n`;
  css += `.text-muted { color: var(--text-muted); }\n`;
  css += `.text-secondary { color: var(--text-secondary); }\n\n`;
  
  // Component styles
  css += `/* Components */\n`;
  css += `.card {\n  background: var(--surface-base);\n  border: 1px solid var(--border-base);\n  border-radius: var(--radius-lg);\n  box-shadow: var(--shadow-base);\n  padding: var(--space-6);\n  transition: all var(--duration-base) var(--duration-ease);\n}\n\n`;
  
  css += `.btn {\n  display: inline-flex;\n  align-items: center;\n  justify-content: center;\n  gap: var(--space-2);\n  padding: var(--space-3) var(--space-4);\n  font-size: var(--font-size-sm);\n  font-weight: var(--font-weight-medium);\n  border: 1px solid var(--border-base);\n  border-radius: var(--radius-md);\n  background: var(--surface-base);\n  color: var(--text-primary);\n  cursor: pointer;\n  transition: all var(--duration-fast) var(--duration-ease);\n  text-decoration: none;\n  user-select: none;\n}\n\n`;
  
  css += `.btn:hover:not(:disabled) {\n  background: var(--surface-hover);\n  border-color: var(--border-hover);\n  box-shadow: var(--shadow-sm);\n}\n\n`;
  
  css += `.btn.primary {\n  background: var(--brand-primary);\n  border-color: var(--brand-primary);\n  color: white;\n}\n\n`;
  
  css += `.btn.primary:hover:not(:disabled) {\n  background: var(--brand-hover);\n  border-color: var(--brand-hover);\n}\n\n`;
  
  css += `.input {\n  width: 100%;\n  padding: var(--space-3) var(--space-4);\n  font-size: var(--font-size-sm);\n  background: var(--surface-base);\n  border: 1px solid var(--border-base);\n  border-radius: var(--radius-md);\n  color: var(--text-primary);\n  transition: all var(--duration-base) var(--duration-ease);\n}\n\n`;
  
  css += `.input:focus {\n  outline: none;\n  border-color: var(--border-focus);\n  box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.1);\n}\n\n`;
  
  css += `.icon-btn {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  width: 48px;\n  height: 48px;\n  border: none;\n  border-radius: var(--radius-lg);\n  background: transparent;\n  color: var(--text-muted);\n  cursor: pointer;\n  transition: all var(--duration-fast) var(--duration-ease);\n}\n\n`;
  
  css += `.icon-btn:hover {\n  background: var(--surface-hover);\n  color: var(--text-primary);\n}\n\n`;
  
  css += `.icon-btn.active {\n  background: var(--brand-primary);\n  color: white;\n}\n\n`;
  
  return css;
}

// Export for Node.js or browser
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { generateCSS };
} else {
  window.generateCSS = generateCSS;
}