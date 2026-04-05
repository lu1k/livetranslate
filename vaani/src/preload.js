const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe, minimal API to the renderer (index.html)
contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize:  () => ipcRenderer.send('window:minimize'),
  maximize:  () => ipcRenderer.send('window:maximize'),
  close:     () => ipcRenderer.send('window:close'),

  // Listen for maximize state changes from main
  onMaxState: (cb) => ipcRenderer.on('window:maxState', (_event, val) => cb(val)),
});
