const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, globalShortcut, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');
const { generateDIcon } = require('./icon');

let mainWindow = null;
let bubbleWindow = null;
let tray = null;
let pythonProcess = null;
let bubbleVisible = true;
let appState = { bubbleVisible: true };

const isDev = !app.isPackaged;
const PYTHON_API = 'http://127.0.0.1:8765';

function appStatePath() {
  return path.join(app.getPath('userData'), 'app-state.json');
}

function readAppState() {
  try {
    const raw = fs.readFileSync(appStatePath(), 'utf8');
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function writeAppState() {
  try {
    fs.writeFileSync(appStatePath(), JSON.stringify(appState, null, 2), 'utf8');
  } catch (err) {
    console.error('[State] Failed to persist:', err.message);
  }
}

function broadcastBubbleVisibility() {
  for (const w of BrowserWindow.getAllWindows()) {
    if (w === bubbleWindow) continue;
    try { w.webContents.send('bubble:visibility', bubbleVisible); } catch {}
  }
}

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
    icon: generateDIcon(256),
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

// Visible bubble diameter. Must stay in sync with --size in electron/bubble.html.
const BUBBLE_SIZE = 160;
// Electron window is oversized so pulse halos + outer rings can fade out past
// the visible bubble without hitting the window edge (which would clip into a
// visible square). BUBBLE_WINDOW - BUBBLE_SIZE = padding on each side / 2.
const BUBBLE_WINDOW = 320;

function createBubbleWindow() {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;

  bubbleWindow = new BrowserWindow({
    width: BUBBLE_WINDOW,
    height: BUBBLE_WINDOW,
    x: screenW - BUBBLE_WINDOW - 20,
    y: screenH - BUBBLE_WINDOW - 20,
    useContentSize: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: true,
    minimizable: false,
    maximizable: false,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'bubble-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  bubbleWindow.loadFile(path.join(__dirname, 'bubble.html'));
  bubbleWindow.setAlwaysOnTop(true, 'screen-saver');
  // Start click-through on the transparent padding; forwarding keeps mousemove
  // firing in the renderer so it can toggle interactivity when the cursor
  // enters the visible bubble.
  bubbleWindow.setIgnoreMouseEvents(true, { forward: true });

  bubbleWindow.on('closed', () => {
    bubbleWindow = null;
  });

  if (bubbleVisible) bubbleWindow.show();
}

function showBubble() {
  if (!bubbleWindow) {
    createBubbleWindow();
    bubbleWindow.show();
  } else {
    bubbleWindow.show();
  }
  bubbleVisible = true;
  appState.bubbleVisible = true;
  writeAppState();
  updateTrayMenu();
  broadcastBubbleVisibility();
}

function hideBubble() {
  if (bubbleWindow) bubbleWindow.hide();
  bubbleVisible = false;
  appState.bubbleVisible = false;
  writeAppState();
  updateTrayMenu();
  broadcastBubbleVisibility();
}

function toggleBubble() {
  if (bubbleVisible) hideBubble();
  else showBubble();
  return bubbleVisible;
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    {
      label: 'Show Deen-Notes',
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
    {
      label: bubbleVisible ? 'Hide desktop bubble' : 'Show desktop bubble',
      click: toggleBubble,
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
}

function updateTrayMenu() {
  if (tray) tray.setContextMenu(buildTrayMenu());
}

function createTray() {
  const trayIcon = generateDIcon(32);
  tray = new Tray(trayIcon);
  tray.setToolTip('Deen-Notes');
  tray.setContextMenu(buildTrayMenu());
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

ipcMain.handle('bubble:toggle', () => toggleBubble());
ipcMain.handle('bubble:set-visible', (_e, v) => {
  if (v) showBubble(); else hideBubble();
  return bubbleVisible;
});
ipcMain.handle('bubble:get-visible', () => bubbleVisible);

ipcMain.handle('bubble:show-main', () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
});
ipcMain.handle('bubble:trigger-note', () => triggerNoteCapture());
ipcMain.on('bubble:set-interactive', (event, interactive) => {
  if (!bubbleWindow) return;
  // When interactive, the window catches clicks on the visible bubble.
  // When not, clicks fall through to whatever is behind, but mousemove is
  // still forwarded so the renderer can detect re-entry.
  bubbleWindow.setIgnoreMouseEvents(!interactive, { forward: true });
});
ipcMain.on('bubble:move', (event, dx, dy) => {
  if (!bubbleWindow) return;
  const [x, y] = bubbleWindow.getPosition();
  // setBounds re-asserts the locked 80x80 size on every move so Chromium's
  // fractional-DPI rounding on Windows can't silently grow the HWND.
  bubbleWindow.setBounds({
    x: Math.round(x + dx),
    y: Math.round(y + dy),
    width: BUBBLE_WINDOW,
    height: BUBBLE_WINDOW,
  });
});

app.whenReady().then(() => {
  appState = readAppState();
  if (typeof appState.bubbleVisible !== 'boolean') appState.bubbleVisible = true;
  bubbleVisible = appState.bubbleVisible;

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
