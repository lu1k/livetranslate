/**
 * electron/window-controls.js
 *
 * Injected only when running inside Electron (detected via window.electronAPI).
 * Adds a slim drag-handle / controls bar at the top of the overlay so the
 * user can move and dismiss the window without a native title bar.
 *
 * Performance: creates ~8 DOM nodes once; no ongoing work.
 */

(function initWindowControls() {
  // Only activate inside Electron
  if (!window.electronAPI) return;

  const STYLES = `
    #wc-bar {
      position: fixed;
      top: 0; left: 0; right: 0;
      height: 28px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      padding: 0 8px;
      gap: 6px;
      background: var(--surface, #0d1317);
      border-bottom: 1px solid var(--border, #1e2d36);
      -webkit-app-region: drag;   /* entire bar is draggable */
      z-index: 9999;
      user-select: none;
    }
    .wc-btn {
      -webkit-app-region: no-drag; /* buttons are clickable, not draggable */
      width: 12px; height: 12px;
      border-radius: 50%;
      border: none;
      cursor: pointer;
      opacity: 0.7;
      transition: opacity 120ms ease;
      padding: 0;
    }
    .wc-btn:hover { opacity: 1; }
    .wc-btn.minimize { background: #f0a02e; }
    .wc-btn.close    { background: #f03c2e; }

    /* Push #app content down so it isn't hidden under the bar */
    #app { padding-top: 28px !important; }
    #shortcut-bar { bottom: 0; }
  `;

  // Inject styles
  const styleEl = document.createElement('style');
  styleEl.textContent = STYLES;
  document.head.appendChild(styleEl);

  // Build the bar
  const bar      = document.createElement('div');
  bar.id         = 'wc-bar';

  // Drag hint label
  const hint = document.createElement('span');
  hint.textContent = 'LiveTranslate';
  hint.style.cssText = 'flex:1;font-size:10px;letter-spacing:.1em;color:var(--text-dim,#4d6e7e);font-family:var(--mono,monospace);padding-left:8px';
  bar.appendChild(hint);

  // Minimize button
  const minBtn = document.createElement('button');
  minBtn.className = 'wc-btn minimize';
  minBtn.title     = 'Minimise';
  minBtn.addEventListener('click', () => window.electronAPI.minimize());
  bar.appendChild(minBtn);

  // Close/hide button (hides to tray, doesn't quit)
  const closeBtn = document.createElement('button');
  closeBtn.className = 'wc-btn close';
  closeBtn.title     = 'Hide overlay (Ctrl+Shift+T to restore)';
  closeBtn.addEventListener('click', () => window.electronAPI.closeOverlay());
  bar.appendChild(closeBtn);

  document.body.prepend(bar);
})();
