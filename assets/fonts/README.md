# Custom Fonts

Upload your TTF font files to this directory.

## Recommended Structure:
```
assets/fonts/
├── primary/          # Main UI font files
├── display/          # Display/heading font files  
├── mono/            # Monospace font files
└── README.md        # This file
```

## Supported Formats:
- TTF (TrueType Font)
- WOFF/WOFF2 (Web Open Font Format) - if available
- OTF (OpenType Font)

## Font Loading:
Fonts will be loaded via CSS `@font-face` declarations and integrated into the design system's font variables in `design/settings.json`.