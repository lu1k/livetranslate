const { app, BrowserWindow, ipcMain, Menu, shell } = require('electron');
const path = require('path');

// Keep a global reference so it doesn't get garbage collected
let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 780,
    minWidth: 860,
    minHeight: 600,
    backgroundColor: '#0c0c0e',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    show: false, // wait for ready-to-show
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Show window gracefully once ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ── App lifecycle ──────────────────────────────────────────
app.whenReady().then(() => {
  createWindow();
  setApplicationMenu();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ── IPC handlers ───────────────────────────────────────────
// Window controls (since we use a frameless window)
ipcMain.on('window:minimize', () => mainWindow?.minimize());
ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.on('window:close', () => mainWindow?.close());

// Forward maximize-state changes to renderer
function broadcastMaxState() {
  if (!mainWindow) return;
  mainWindow.webContents.send('window:maxState', mainWindow.isMaximized());
}
app.on('browser-window-created', (_, win) => {
  win.on('maximize',   broadcastMaxState);
  win.on('unmaximize', broadcastMaxState);
});

// ── Custom application menu ─────────────────────────────────
function setApplicationMenu() {
  const template = [
    {
      label: 'VAANI',
      submenu: [
        { label: 'About VAANI', role: 'about' },
        { type: 'separator' },
        { label: 'Quit', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', role: 'reload' },
        { label: 'Toggle DevTools', accelerator: 'CmdOrCtrl+Shift+I', role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}
