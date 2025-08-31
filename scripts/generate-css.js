// Generate CSS from settings.json
const fs = require('fs');
const path = require('path');

const settingsPath = path.join(__dirname, '../design/settings.json');
const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));

function generateCSS(settings) {
  const theme = settings.theme;
  
  let css = '/* Auto-generated from design/settings.json */\n:root {\n';
  
  // Colors
  css += '  /* Colors */\n';
  css += `  --bg-primary: ${theme.colors.background.primary};\n`;
  css += `  --bg-secondary: ${theme.colors.background.secondary};\n`;
  css += `  --bg-tertiary: ${theme.colors.background.tertiary};\n`;
  css += `  --surface-base: ${theme.colors.surface.default};\n`;
  css += `  --surface-hover: ${theme.colors.surface.hover};\n`;
  css += `  --surface-active: ${theme.colors.surface.active};\n`;
  css += `  --text-primary: ${theme.colors.text.primary};\n`;
  css += `  --text-secondary: ${theme.colors.text.secondary};\n`;
  css += `  --text-muted: ${theme.colors.text.muted};\n`;
  css += `  --text-disabled: ${theme.colors.text.disabled};\n`;
  css += `  --border-base: ${theme.colors.border.default};\n`;
  css += `  --border-hover: ${theme.colors.border.hover};\n`;
  css += `  --border-focus: ${theme.colors.border.focus};\n`;
  css += `  --brand-primary: ${theme.colors.brand.primary};\n`;
  css += `  --brand-hover: ${theme.colors.brand.hover};\n`;
  css += `  --brand-active: ${theme.colors.brand.active};\n`;
  css += `  --success: ${theme.colors.status.success};\n`;
  css += `  --success-bg: ${theme.colors.status.successBg};\n`;
  css += `  --warning: ${theme.colors.status.warning};\n`;
  css += `  --warning-bg: ${theme.colors.status.warningBg};\n`;
  css += `  --error: ${theme.colors.status.error};\n`;
  css += `  --error-bg: ${theme.colors.status.errorBg};\n`;
  css += `  --info: ${theme.colors.status.info};\n`;
  css += `  --info-bg: ${theme.colors.status.infoBg};\n`;
  
  // Typography
  css += '\n  /* Typography */\n';
  css += `  --font-family: ${theme.typography.fontFamily};\n`;
  css += `  --font-display: ${theme.typography.fontDisplay};\n`;
  css += `  --font-mono: ${theme.typography.fontMono};\n`;
  css += `  --font-size-xs: ${theme.typography.fontSize.xs};\n`;
  css += `  --font-size-sm: ${theme.typography.fontSize.sm};\n`;
  css += `  --font-size-base: ${theme.typography.fontSize.base};\n`;
  css += `  --font-size-lg: ${theme.typography.fontSize.lg};\n`;
  css += `  --font-size-xl: ${theme.typography.fontSize.xl};\n`;
  css += `  --font-size-2xl: ${theme.typography.fontSize['2xl']};\n`;
  css += `  --font-size-3xl: ${theme.typography.fontSize['3xl']};\n`;
  css += `  --font-weight-normal: ${theme.typography.fontWeight.normal};\n`;
  css += `  --font-weight-medium: ${theme.typography.fontWeight.medium};\n`;
  css += `  --font-weight-semibold: ${theme.typography.fontWeight.semibold};\n`;
  css += `  --font-weight-bold: ${theme.typography.fontWeight.bold};\n`;
  css += `  --line-height-tight: ${theme.typography.lineHeight.tight};\n`;
  css += `  --line-height-base: ${theme.typography.lineHeight.base};\n`;
  css += `  --line-height-relaxed: ${theme.typography.lineHeight.relaxed};\n`;
  
  // Spacing
  css += '\n  /* Spacing */\n';
  Object.entries(theme.spacing).forEach(([key, value]) => {
    css += `  --space-${key}: ${value};\n`;
  });
  
  // Border radius
  css += '\n  /* Border Radius */\n';
  Object.entries(theme.borderRadius).forEach(([key, value]) => {
    css += `  --radius-${key}: ${value};\n`;
  });
  
  // Shadows
  css += '\n  /* Shadows */\n';
  Object.entries(theme.shadows).forEach(([key, value]) => {
    css += `  --shadow-${key}: ${value};\n`;
  });
  
  // Transitions
  css += '\n  /* Transitions */\n';
  css += `  --duration-fast: ${theme.transitions.fast};\n`;
  css += `  --duration-base: ${theme.transitions.base};\n`;
  css += `  --duration-slow: ${theme.transitions.slow};\n`;
  css += `  --ease: ${theme.transitions.ease};\n`;
  
  // Layout
  css += '\n  /* Layout */\n';
  css += `  --sidebar-width: ${settings.layout.sidebar.width};\n`;
  css += `  --chatbox-width: ${settings.layout.chatbox.width};\n`;
  
  css += '}\n';
  
  return css;
}

const generatedCSS = generateCSS(settings);
console.log(generatedCSS);