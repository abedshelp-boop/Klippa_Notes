const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, globalShortcut, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow = null;
let bubbleWindow = null;
let tray = null;
let pythonProcess = null;

const isDev = !app.isPackaged;
const PYTHON_API = 'http://127.0.0.1:8765';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0f0f0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

function createBubbleWindow() {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;

  bubbleWindow = new BrowserWindow({
    width: 80,
    height: 80,
    x: screenW - 100,
    y: screenH - 100,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      preload: path.join(__dirname, 'bubble-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  bubbleWindow.loadFile(path.join(__dirname, 'bubble.html'));
  bubbleWindow.setAlwaysOnTop(true, 'screen-saver');

  bubbleWindow.on('closed', () => {
    bubbleWindow = null;
  });
}

function createTray() {
  const iconPath = path.join(__dirname, '..', 'assets', 'icon.png');
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Klippa',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: 'Capture Note (Ctrl+Shift+N)',
      click: triggerNoteCapture,
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setToolTip('Klippa - Listening...');
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function triggerNoteCapture() {
  const postData = JSON.stringify({});
  const options = {
    hostname: '127.0.0.1',
    port: 8765,
    path: '/trigger',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Content-Length': Buffer.byteLength(postData),
    },
  };

  const req = http.request(options, (res) => {
    let body = '';
    res.on('data', (chunk) => { body += chunk; });
    res.on('end', () => {
      console.log('[Trigger] Response:', body);
    });
  });

  req.on('error', (err) => {
    console.error('[Trigger] Failed - Python service not ready:', err.message);
  });

  req.write(postData);
  req.end();
}

function registerGlobalShortcut() {
  globalShortcut.register('CommandOrControl+Shift+N', () => {
    console.log('[Shortcut] Ctrl+Shift+N pressed - triggering note capture');
    triggerNoteCapture();
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

function startPythonService() {
  const pythonPath = path.join(
    __dirname, '..', 'python-service', 'venv', 'Scripts', 'python.exe'
  );

  const scriptPath = path.join(__dirname, '..', 'python-service', 'main.py');

  console.log('[Python] Starting:', pythonPath, scriptPath);

  pythonProcess = spawn(pythonPath, ['-u', scriptPath], {
    cwd: path.join(__dirname, '..'),
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python ERROR] ${data.toString().trim()}`);
  });

  pythonProcess.on('error', (err) => {
    console.error(`[Python] Failed to start: ${err.message}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Process exited with code ${code}`);
    if (code !== 0 && !app.isQuitting) {
      console.log('[Python] Restarting in 3 seconds...');
      setTimeout(startPythonService, 3000);
    }
  });
}

function stopPythonService() {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.handle('window:close', () => mainWindow?.hide());
ipcMain.handle('trigger-note', () => triggerNoteCapture());

ipcMain.handle('bubble:show-main', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});
ipcMain.handle('bubble:trigger-note', () => triggerNoteCapture());
ipcMain.on('bubble:move', (event, dx, dy) => {
  if (!bubbleWindow) return;
  const [x, y] = bubbleWindow.getPosition();
  bubbleWindow.setPosition(x + dx, y + dy);
});

app.whenReady().then(() => {
  createWindow();
  createBubbleWindow();
  createTray();
  registerGlobalShortcut();
  startPythonService();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('before-quit', () => {
  app.isQuitting = true;
  stopPythonService();
});

app.on('window-all-closed', (e) => {
  // Don't quit -- the tray and bubble keep the app alive
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
