# Frontend Changes — Dark/Light Theme Toggle

## Summary
Added a dark/light theme toggle button that allows users to switch between themes. The chosen theme is persisted in `localStorage` across sessions.

---

## Files Modified

### `index.html`
- Updated CSS/JS cache-busting version query strings (`?v=10` → `?v=11`).
- Added a `<button id="themeToggle">` element with two inline SVG icons:
  - **Moon icon** — displayed in dark mode (default); clicking switches to light mode.
  - **Sun icon** — displayed in light mode; clicking switches back to dark mode.
- Button is positioned just before the closing `<body>` tag so it renders on top of all content.
- Includes `aria-label` and `aria-hidden` attributes for accessibility.

### `style.css`
- **Light theme variables** — Added a `[data-theme="light"]` block that overrides all CSS custom properties with light-mode equivalents:
  - `--background: #f8fafc` / `--surface: #ffffff` / `--surface-hover: #f1f5f9`
  - `--text-primary: #0f172a` / `--text-secondary: #64748b`
  - `--border-color: #e2e8f0`
  - Adjusted shadow opacity and focus-ring for lighter backgrounds.
  - `--welcome-bg: #eff6ff` / `--welcome-border: #93c5fd`
- **Transition on `body`** — Added `transition: background-color 0.3s ease, color 0.3s ease` for a smooth global colour shift.
- **Transition on key elements** — Added a targeted transition rule (background, color, border, shadow) to `.sidebar`, `.chat-messages`, `.message-content`, `.suggested-item`, `.stat-item`, `#chatInput`, `#sendButton`, and others so every visible surface animates smoothly.
- **`.theme-toggle` button** — `position: fixed; top: 1rem; right: 1rem` places it in the top-right corner at `z-index: 1000`. Styles include:
  - 44 × 44 px circular button with a subtle border and shadow.
  - Hover: background tint, primary-colour border, `scale(1.05)`.
  - Focus: 3 px focus ring using `--focus-ring` for keyboard navigation.
  - Active: `scale(0.97)` press-down feedback.
- **Icon visibility rules** — `.sun-icon` is `display: none` by default (dark mode); `.moon-icon` is shown. Under `[data-theme="light"]` these are swapped.

### `script.js`
- **IIFE `initTheme()`** — Runs immediately (before `DOMContentLoaded`) to read `localStorage.getItem('theme')` and apply `data-theme` to `document.documentElement`, preventing a flash of the wrong theme on page load.
- **`themeToggle` variable** — Added to the DOM elements list and wired up in `setupEventListeners()`.
- **`toggleTheme()` function** — Reads the current `data-theme` value, flips it between `"dark"` and `"light"`, writes the new value back to the `<html>` element and to `localStorage`. Also updates `aria-label` dynamically to indicate the next action.
