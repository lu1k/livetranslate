/**
 * electron/main.js — Electron main process
 *
 * Responsibilities:
 *  - Create the overlay BrowserWindow (frameless, transparent, always-on-top)
 *  - Manage system tray icon for show/hide/quit
 *  - Handle IPC from renderer (permission checks, window controls)
 *  - Register global keyboard shortcut (Ctrl/Cmd+Shift+T) to toggle overlay
 *  - Cleanly tear down on quit
 */

const {
  app,
  BrowserWindow,
  ipcMain,
  Tray,
  Menu,
  globalShortcut,
  shell,
  screen,
} = require('electron');
const path = require('path');

// ── Dev flag: set via `npm run dev` ─────────────────────────
const isDev = process.argv.includes('--dev');

// ── Module-level refs (prevent GC) ──────────────────────────
let mainWindow = null;
let tray       = null;

// ── Window factory ──────────────────────────────────────────
function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    // --- Size & position: bottom-right corner by default ---
    width:  480,
    height: 620,
    x: width  - 496,
    y: height - 636,

    // --- Overlay appearance ---
    frame:       false,          // No OS title bar
    transparent: true,           // CSS transparent body shows through
    alwaysOnTop: true,           // Sits above other apps
    resizable:   true,
    movable:     true,
    skipTaskbar: false,          // Keep in taskbar for discoverability

    // --- Security ---
    webPreferences: {
      preload:              path.join(__dirname, 'preload.js'),
      contextIsolation:     true,   // Isolate renderer from Node
      nodeIntegration:      false,  // No Node in renderer
      webSecurity:          true,
      allowRunningInsecureContent: false,
    },

    // --- Hide until ready to avoid flash of unstyled content ---
    show: false,
  });

  // Load the frontend
  mainWindow.loadFile(path.join(__dirname, '..', 'index.html'));

  // Show only once fully rendered
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  // Keep ref alive; null on close so GC can collect
  mainWindow.on('closed', () => { mainWindow = null; });

  // Prevent navigation away from the app (security)
  mainWindow.webContents.on('will-navigate', (e, url) => {
    // Allow hash-based routing within the app
    const appUrl = `file://${path.resolve(__dirname, '..', 'index.html')}`;
    if (!url.startsWith(appUrl) && !url.startsWith('file://')) {
      e.preventDefault();
      shell.openExternal(url); // Open external URLs in default browser
    }
  });
}

// ── Tray icon ────────────────────────────────────────────────
function createTray() {
  // Fallback to a named icon; replace with your asset path
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');

  // Use a default nativeImage if asset is missing (dev convenience)
  let trayIcon;
  try {
    const { nativeImage } = require('electron');
    trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) throw new Error('empty');
  } catch {
    // Minimal 16×16 placeholder icon (1-pixel green dot encoded as PNG)
    const { nativeImage } = require('electron');
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('LiveTranslate Overlay');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show / Hide',
      click: toggleWindow,
    },
    {
      label: 'Always on Top',
      type: 'checkbox',
      checked: true,
      click: (item) => {
        if (mainWindow) mainWindow.setAlwaysOnTop(item.checked);
      },
    },
    { type: 'separator' },
    {
      label: 'Opacity',
      submenu: [100, 90, 75, 50].map(pct => ({
        label: `${pct}%`,
        type: 'radio',
        checked: pct === 100,
        click: () => { if (mainWindow) mainWindow.setOpacity(pct / 100); },
      })),
    },
    { type: 'separator' },
    {
      label: 'Quit LiveTranslate',
      click: () => app.quit(),
    },
  ]);

  tray.setContextMenu(contextMenu);
  // Left-click tray icon also toggles window
  tray.on('click', toggleWindow);
}

function toggleWindow() {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) mainWindow.hide();
  else mainWindow.show();
}

// ── Global shortcut ──────────────────────────────────────────
function registerShortcuts() {
  // Ctrl+Shift+T (Win/Linux) or Cmd+Shift+T (Mac) toggles overlay
  const ret = globalShortcut.register('CommandOrControl+Shift+T', toggleWindow);
  if (!ret && isDev) console.warn('[main] Global shortcut registration failed');
}

// ── IPC handlers (renderer → main) ──────────────────────────
function registerIPC() {
  // Window control actions sent from renderer via preload bridge
  ipcMain.on('window:minimize', () => mainWindow?.minimize());
  ipcMain.on('window:close',    () => mainWindow?.hide()); // Hide, don't quit
  ipcMain.on('window:quit',     () => app.quit());

  // Opacity control from renderer UI (if added later)
  ipcMain.on('window:opacity', (_e, value) => {
    if (mainWindow && typeof value === 'number') {
      mainWindow.setOpacity(Math.max(0.2, Math.min(1, value)));
    }
  });

  // Always-on-top toggle from renderer
  ipcMain.on('window:alwaysOnTop', (_e, value) => {
    mainWindow?.setAlwaysOnTop(Boolean(value));
  });
}

// ── App lifecycle ────────────────────────────────────────────
app.whenReady().then(() => {
  createWindow();
  createTray();
  registerShortcuts();
  registerIPC();

  // macOS: re-create window if dock icon clicked and no windows open
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Quit when all windows closed (except macOS — keep in tray)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Release global shortcuts on quit
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

// ── Permissions: grant mic and camera ────────────────────────
// Must be set BEFORE the window navigates to a page that requests them
app.on('web-contents-created', (_e, contents) => {
  contents.session.setPermissionRequestHandler(
    (_webContents, permission, callback) => {
      // Allow mic and camera; deny everything else by default
      const allowed = ['media', 'microphone', 'camera'];
      callback(allowed.includes(permission));
    }
  );
});
