/**
 * URL Formatting Utilities
 * 
 * Provides helper functions to format URLs consistently across the application
 * with styling from the settings file.
 */

/**
 * Load settings from the design/settings.json file
 * @returns {Promise<Object>} The settings object
 */
async function loadSettings() {
    try {
        const response = await fetch('./design/settings.json');
        return await response.json();
    } catch (error) {
        console.warn('Could not load settings, using defaults:', error);
        return {
            theme: {
                colors: {
                    link: {
                        primary: '#1d4ed8',
                        hover: '#2563eb',
                        visited: '#7c3aed',
                        underlineColor: '#1d4ed8'
                    }
                }
            }
        };
    }
}

/**
 * URL regex pattern to detect URLs in text
 */
const URL_REGEX = /(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*))/g;

/**
 * Format a single URL as a clickable [here] link
 * @param {string} url - The URL to format
 * @param {Object} linkColors - Link colors from settings
 * @param {string} [linkText='here'] - Text to display for the link
 * @returns {string} HTML string for the formatted link
 */
function formatSingleUrl(url, linkColors, linkText = 'here') {
    const styles = [
        `color: ${linkColors.primary}`,
        `text-decoration: underline`,
        `text-decoration-color: ${linkColors.underlineColor}`,
        `cursor: pointer`,
        `transition: color 0.2s ease`
    ].join('; ');

    const hoverStyles = `
        onmouseover="this.style.color='${linkColors.hover}'"
        onmouseout="this.style.color='${linkColors.primary}'"
    `;

    return `<a href="${url}" target="_blank" rel="noopener noreferrer" style="${styles}" ${hoverStyles}>[${linkText}]</a>`;
}

/**
 * Replace all URLs in text with [here] links
 * @param {string} text - Text containing URLs to format
 * @param {string} [linkText='here'] - Text to display for links
 * @returns {Promise<string>} Text with URLs replaced by formatted links
 */
async function formatUrlsInText(text, linkText = 'here') {
    if (typeof text !== 'string') return text;
    
    const settings = await loadSettings();
    const linkColors = settings.theme?.colors?.link || {
        primary: '#1d4ed8',
        hover: '#2563eb',
        underlineColor: '#1d4ed8'
    };

    return text.replace(URL_REGEX, (match, url) => {
        return formatSingleUrl(url, linkColors, linkText);
    });
}

/**
 * Format URLs in text with different link text for different URLs
 * @param {string} text - Text containing URLs to format
 * @param {Object} urlTextMap - Map of URL patterns to link text
 * @returns {Promise<string>} Text with URLs replaced by formatted links
 */
async function formatUrlsWithCustomText(text, urlTextMap = {}) {
    if (typeof text !== 'string') return text;
    
    const settings = await loadSettings();
    const linkColors = settings.theme?.colors?.link || {
        primary: '#1d4ed8',
        hover: '#2563eb',
        underlineColor: '#1d4ed8'
    };

    return text.replace(URL_REGEX, (match, url) => {
        // Find custom text for this URL
        let linkText = 'here'; // default
        for (const [pattern, customText] of Object.entries(urlTextMap)) {
            if (url.includes(pattern)) {
                linkText = customText;
                break;
            }
        }
        
        return formatSingleUrl(url, linkColors, linkText);
    });
}

/**
 * Create CSS classes for URL styling that can be added to stylesheets
 * @returns {Promise<string>} CSS string for URL styling
 */
async function generateUrlCss() {
    const settings = await loadSettings();
    const linkColors = settings.theme?.colors?.link || {
        primary: '#1d4ed8',
        hover: '#2563eb',
        visited: '#7c3aed',
        underlineColor: '#1d4ed8'
    };

    return `
        .url-link {
            color: ${linkColors.primary};
            text-decoration: underline;
            text-decoration-color: ${linkColors.underlineColor};
            cursor: pointer;
            transition: color 0.2s ease;
        }
        
        .url-link:hover {
            color: ${linkColors.hover};
        }
        
        .url-link:visited {
            color: ${linkColors.visited};
        }
        
        .url-link:focus {
            outline: 2px solid ${linkColors.primary};
            outline-offset: 2px;
        }
    `;
}

/**
 * Apply URL formatting to a DOM element
 * @param {HTMLElement} element - The DOM element to process
 * @param {string} [linkText='here'] - Text to display for links
 */
async function formatUrlsInElement(element, linkText = 'here') {
    if (!element || !element.innerHTML) return;
    
    const formattedHtml = await formatUrlsInText(element.innerHTML, linkText);
    element.innerHTML = formattedHtml;
}

/**
 * Utility function to check if a string contains URLs
 * @param {string} text - Text to check
 * @returns {boolean} True if text contains URLs
 */
function containsUrls(text) {
    return typeof text === 'string' && URL_REGEX.test(text);
}

/**
 * Extract all URLs from text
 * @param {string} text - Text to extract URLs from
 * @returns {string[]} Array of URLs found in the text
 */
function extractUrls(text) {
    if (typeof text !== 'string') return [];
    
    const matches = text.match(URL_REGEX);
    return matches || [];
}

// Export for use across the application
if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        formatUrlsInText,
        formatUrlsWithCustomText,
        formatUrlsInElement,
        generateUrlCss,
        containsUrls,
        extractUrls,
        loadSettings
    };
} else {
    // Browser environment
    window.UrlFormatter = {
        formatUrlsInText,
        formatUrlsWithCustomText,
        formatUrlsInElement,
        generateUrlCss,
        containsUrls,
        extractUrls,
        loadSettings
    };
}