/**
 * electron/preload.js — Context-isolated preload script
 *
 * Exposes a minimal, typed API surface to the renderer via
 * contextBridge. The renderer never touches Node or Electron
 * internals directly — only what's explicitly exposed here.
 *
 * Security rationale:
 *  - contextIsolation: true means renderer JS and preload JS
 *    run in separate JS contexts (V8 contexts), so the renderer
 *    cannot reach Node globals even if XSS occurred.
 *  - Only whitelisted channels are forwarded over IPC.
 */

const { contextBridge, ipcRenderer } = require('electron');

// ── Whitelist of channels the renderer may send ──────────────
const ALLOWED_SEND = new Set([
  'window:minimize',
  'window:close',
  'window:quit',
  'window:opacity',
  'window:alwaysOnTop',
]);

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Send a one-way message to the main process.
   * Only channels in the whitelist are forwarded.
   */
  send(channel, ...args) {
    if (ALLOWED_SEND.has(channel)) {
      ipcRenderer.send(channel, ...args);
    } else {
      console.warn(`[preload] Blocked IPC send on unknown channel: ${channel}`);
    }
  },

  /** Convenience wrappers used by the renderer window-controls bar */
  minimize:     () => ipcRenderer.send('window:minimize'),
  closeOverlay: () => ipcRenderer.send('window:close'),
  quit:         () => ipcRenderer.send('window:quit'),
  setOpacity:   (v) => ipcRenderer.send('window:opacity', v),
  setAlwaysOnTop: (v) => ipcRenderer.send('window:alwaysOnTop', v),

  /** Expose platform so renderer can adjust UI if needed */
  platform: process.platform,   // 'win32' | 'darwin' | 'linux'
});
