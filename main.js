// main.js
const { app, BrowserWindow, shell } = require('electron');
const path = require('path');

// WSL-friendly: prefer software rendering
app.disableHardwareAcceleration();
app.commandLine.appendSwitch('disable-gpu');
// If needed later:
// app.commandLine.appendSwitch('in-process-gpu');
// app.commandLine.appendSwitch('no-sandbox');

function createWindow() {
  const win = new BrowserWindow({
    width: 1650,
    height: 1050,
    show: true,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.loadFile('index.html');
  
  // Development: disable cache and enable reload
  // Only open DevTools if explicitly in development mode
  if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
    win.webContents.openDevTools();
  }
  
  // Always enable Ctrl+R reload for convenience
  win.webContents.on('before-input-event', (event, input) => {
    if (input.control && input.key.toLowerCase() === 'r') {
      win.reload();
    }
  });

  // Block random navigations/popups; open external links in the OS browser
  win.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const u = new URL(url);
      if (u.protocol === 'https:' || u.protocol === 'http:') {
        shell.openExternal(url);
      }
    } catch (_) {}
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
