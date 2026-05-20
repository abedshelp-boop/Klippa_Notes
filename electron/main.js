const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, globalShortcut, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const http = require('http');
const { generateDIcon } = require('./icon');
const { createDebug } = require('./debug');

// Phase 12: prefer the static logo asset (assets/icon-256.png +
// build/icon.ico) over the legacy programmatic "D" generator. The
// programmatic one remains as a fallback so dev environments without the
// generated assets still launch with an icon instead of a Chromium default.
const ICON_ICO_PATH = path.join(__dirname, '..', 'build', 'icon.ico');
const ICON_PNG_PATH = path.join(__dirname, '..', 'assets', 'icon-256.png');

function loadAppIcon(fallbackSize) {
  // Try the multi-res .ico first (Windows preferred), then the PNG, then
  // the programmatic fallback.
  if (fs.existsSync(ICON_ICO_PATH)) {
    const img = nativeImage.createFromPath(ICON_ICO_PATH);
    if (!img.isEmpty()) return img;
  }
  if (fs.existsSync(ICON_PNG_PATH)) {
    const img = nativeImage.createFromPath(ICON_PNG_PATH);
    if (!img.isEmpty()) return img;
  }
  return generateDIcon(fallbackSize);
}

let mainWindow = null;
let bubbleWindow = null;
let pickerWindow = null;
let tray = null;
let pythonProcess = null;
let bubbleVisible = true;
let appState = {
  bubbleVisible: true,
  activeTarget: { note_id: null, create_new_pending: false },
  outputLanguage: { code: 'auto', label: 'Global', emoji: '🌍' },
};

const isDev = !app.isPackaged;
const debug = createDebug(isDev);
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
    icon: loadAppIcon(256),
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  if (isDev) {
    // Open DevTools alongside the renderer so debugger + Components tab is
    // the FIRST reflex when something looks wrong, not the last.
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // Phase 6: grant microphone permission so the renderer's
  // navigator.mediaDevices.getUserMedia({ audio: true }) call succeeds.
  // Without this, Chromium silently rejects the prompt in a frameless
  // BrowserWindow and push-to-talk has no audio to send.
  mainWindow.webContents.session.setPermissionRequestHandler(
    (_wc, permission, callback) => {
      // Allow only mic; everything else is denied by default.
      callback(permission === 'media');
    },
  );

  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

// Visible bubble (rounded square) edge length. Sync with --box in bubble.html.
const BUBBLE_SIZE = 48;
// Window dimensions — sync with --window-w / --window-h in bubble.html.
// The window is wider than the box so the "Change file" hover tooltip can
// fade in on the left side without clipping. Extra height absorbs the
// listening pulse halos and the listening outer-glow without clipping —
// listening halo scales to 1.75× = 84px, plus ~25px glow on each side, so
// 140px tall gives breathing room. Width grew correspondingly.
const BUBBLE_WINDOW_W = 260;
const BUBBLE_WINDOW_H = 140;
// Distance from the right edge of the window to the right edge of the box.
// Sync with --right-pad in bubble.html. Picker anchoring uses this.
const BUBBLE_RIGHT_PAD = 26;

// Picker window — small popover that appears just above the bubble when the
// user clicks the sphere. Lists existing notes + a "+ Create new file" row.
// Closes on blur or explicit selection.
const PICKER_WIDTH = 300;
const PICKER_HEIGHT = 480;

function pickerPositionForBubble() {
  if (!bubbleWindow) {
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
    return { x: sw - PICKER_WIDTH - 20, y: sh - PICKER_HEIGHT - 160 };
  }
  const [bx, by] = bubbleWindow.getPosition();
  // The visible box sits at the right edge of the bubble window (inset by
  // BUBBLE_RIGHT_PAD). Right-align the picker to the box so it grows
  // leftward, regardless of where the user has dragged the bubble.
  const boxRightOnScreen = bx + BUBBLE_WINDOW_W - BUBBLE_RIGHT_PAD;
  const x = Math.round(boxRightOnScreen - PICKER_WIDTH);
  const y = Math.round(by - PICKER_HEIGHT + 10);
  return { x, y };
}

function createPickerWindow() {
  const { x, y } = pickerPositionForBubble();

  pickerWindow = new BrowserWindow({
    width: PICKER_WIDTH,
    height: PICKER_HEIGHT,
    x,
    y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'picker-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  pickerWindow.loadFile(path.join(__dirname, 'picker.html'));
  pickerWindow.setAlwaysOnTop(true, 'screen-saver');

  pickerWindow.on('blur', () => {
    if (pickerWindow && pickerWindow.isVisible()) pickerWindow.hide();
  });

  pickerWindow.on('closed', () => {
    pickerWindow = null;
  });
}

function showPicker() {
  if (!pickerWindow) createPickerWindow();
  const { x, y } = pickerPositionForBubble();
  pickerWindow.setPosition(x, y);
  pickerWindow.show();
  pickerWindow.focus();
}

function hidePicker() {
  if (pickerWindow) pickerWindow.hide();
}

// ── Language picker — sibling to the file picker, separate window so
//    each has a focused responsibility and can evolve independently. ────────
const LANG_PICKER_WIDTH = 280;
const LANG_PICKER_HEIGHT = 460;

let langPickerWindow = null;

function langPickerPositionForBubble() {
  if (!bubbleWindow) {
    const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
    return { x: sw - LANG_PICKER_WIDTH - 20, y: sh - LANG_PICKER_HEIGHT - 160 };
  }
  const [bx, by] = bubbleWindow.getPosition();
  const boxRightOnScreen = bx + BUBBLE_WINDOW_W - BUBBLE_RIGHT_PAD;
  const x = Math.round(boxRightOnScreen - LANG_PICKER_WIDTH);
  const y = Math.round(by - LANG_PICKER_HEIGHT + 10);
  return { x, y };
}

function createLangPickerWindow() {
  const { x, y } = langPickerPositionForBubble();

  langPickerWindow = new BrowserWindow({
    width: LANG_PICKER_WIDTH,
    height: LANG_PICKER_HEIGHT,
    x, y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'picker-language-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  langPickerWindow.loadFile(path.join(__dirname, 'picker-language.html'));
  langPickerWindow.setAlwaysOnTop(true, 'screen-saver');

  langPickerWindow.on('blur', () => {
    if (langPickerWindow && langPickerWindow.isVisible()) langPickerWindow.hide();
  });

  langPickerWindow.on('closed', () => {
    langPickerWindow = null;
  });
}

function showLangPicker() {
  if (!langPickerWindow) createLangPickerWindow();
  const { x, y } = langPickerPositionForBubble();
  langPickerWindow.setPosition(x, y);
  langPickerWindow.show();
  langPickerWindow.focus();
}

function hideLangPicker() {
  if (langPickerWindow) langPickerWindow.hide();
}

// ── HTTP helpers for talking to the Python service ───────────────────────
function pythonRequest(method, urlPath, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const options = {
      hostname: '127.0.0.1',
      port: 8765,
      path: urlPath,
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (data) options.headers['Content-Length'] = Buffer.byteLength(data);

    const req = http.request(options, (res) => {
      let raw = '';
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => {
        try {
          resolve(raw ? JSON.parse(raw) : null);
        } catch (e) {
          resolve(raw);
        }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

// Push the persisted target into Python on startup. Python's target state
// is in-memory, so on every Electron launch we re-assert what the user last
// picked. Retries because the Python service takes a few seconds to come up.
async function restoreTargetToPython() {
  const target = appState.activeTarget || { note_id: null, create_new_pending: false };
  // Only bother POSTing if there's actually something to restore.
  if (!target.note_id && !target.create_new_pending) return;

  for (let i = 0; i < 20; i++) {
    try {
      await pythonRequest('POST', '/target', target);
      console.log('[Target] Restored to Python:', target);
      return;
    } catch (err) {
      await new Promise((r) => setTimeout(r, 750));
    }
  }
  console.warn('[Target] Failed to restore target — Python never came up.');
}

// Mirrors restoreTargetToPython: re-asserts the persisted language to the
// fresh Python service on every app launch. Always POSTs (even the default
// "auto") so Python's in-memory state matches Electron's truth even if a
// previous session left Python with a different value.
async function restoreLanguageToPython() {
  const lang = appState.outputLanguage || { code: 'auto', label: 'Global', emoji: '🌍' };
  for (let i = 0; i < 20; i++) {
    try {
      await pythonRequest('POST', '/language', lang);
      console.log('[Language] Restored to Python:', lang);
      return;
    } catch (err) {
      await new Promise((r) => setTimeout(r, 750));
    }
  }
  console.warn('[Language] Failed to restore — Python never came up.');
}

function createBubbleWindow() {
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;

  bubbleWindow = new BrowserWindow({
    width: BUBBLE_WINDOW_W,
    height: BUBBLE_WINDOW_H,
    x: screenW - BUBBLE_WINDOW_W - 20,
    y: screenH - BUBBLE_WINDOW_H - 20,
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
  // Use the new branded asset; the tray needs a smaller size, so resize
  // the loaded image so Windows doesn't subsample a 256px image badly.
  const baseIcon = loadAppIcon(32);
  const trayIcon = baseIcon.resize({ width: 32, height: 32, quality: 'best' });
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

// Rotates python.log -> python.log.1 on each start so the previous session is
// still readable after a crash-restart loop. Returns an open fs.WriteStream.
function openPythonLogStream() {
  const logDir = app.getPath('userData');
  fs.mkdirSync(logDir, { recursive: true });
  const logPath = path.join(logDir, 'python.log');
  const prevPath = path.join(logDir, 'python.log.1');
  try { if (fs.existsSync(logPath)) fs.renameSync(logPath, prevPath); } catch {}
  const stream = fs.createWriteStream(logPath, { flags: 'a' });
  stream.write(`\n===== python service started ${new Date().toISOString()} =====\n`);
  console.log('[Python] Log file:', logPath);
  return stream;
}

let pythonLogStream = null;

// In packaged builds, electron-builder copies python-service/ to process.resourcesPath (extraResources).
function getPythonServicePath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'python-service');
  }
  return path.join(__dirname, '..', 'python-service');
}

function startPythonService() {
  const pyDir = getPythonServicePath();
  const pythonPath = path.join(pyDir, 'venv', 'Scripts', 'python.exe');
  const scriptPath = path.join(pyDir, 'main.py');

  console.log('[Python] Starting:', pythonPath, scriptPath);

  if (!pythonLogStream) pythonLogStream = openPythonLogStream();

  pythonProcess = spawn(pythonPath, ['-u', scriptPath], {
    cwd: pyDir,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      DEEN_NOTES_DATA_DIR: app.getPath('userData'),
      ...(isDev ? { DEEN_DEV: '1' } : {}),
    },
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  pythonProcess.stdout.on('data', (data) => {
    const text = data.toString();
    console.log(`[Python] ${text.trimEnd()}`);
    pythonLogStream?.write(text);
  });

  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString();
    console.error(`[Python ERROR] ${text.trimEnd()}`);
    pythonLogStream?.write(`[stderr] ${text}`);
  });

  pythonProcess.on('error', (err) => {
    console.error(`[Python] Failed to start: ${err.message}`);
    pythonLogStream?.write(`[spawn-error] ${err.message}\n`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Process exited with code ${code}`);
    pythonLogStream?.write(`[exit] code=${code}\n`);
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

// ── Picker IPC ───────────────────────────────────────────────────────────
ipcMain.handle('picker:open', () => {
  showPicker();
});

ipcMain.handle('picker:close', () => {
  hidePicker();
});

ipcMain.handle('picker:list-notes', async () => {
  try {
    return await pythonRequest('GET', '/notes/list', null);
  } catch (err) {
    console.error('[Picker] list-notes failed:', err.message);
    return [];
  }
});

// Phase 10: single round-trip fetch for the tree picker.
ipcMain.handle('picker:tree', async () => {
  try {
    const [notes, groups] = await Promise.all([
      pythonRequest('GET', '/notes/list', null),
      pythonRequest('GET', '/groups', null),
    ]);
    return { notes: notes || [], groups: groups || [] };
  } catch (err) {
    console.error('[Picker] tree fetch failed:', err.message);
    return { notes: [], groups: [] };
  }
});

ipcMain.handle('picker:get-target', async () => {
  try {
    return await pythonRequest('GET', '/target', null);
  } catch (err) {
    return { note_id: null, create_new_pending: false, title: null };
  }
});

ipcMain.handle('picker:select', async (_e, noteId) => {
  const body = { note_id: noteId || null, create_new_pending: false };
  appState.activeTarget = { note_id: body.note_id, create_new_pending: false };
  writeAppState();
  try {
    await pythonRequest('POST', '/target', body);
  } catch (err) {
    console.error('[Picker] select POST failed:', err.message);
  }
  hidePicker();
});

ipcMain.handle('picker:create-new', async () => {
  const body = { note_id: null, create_new_pending: true };
  appState.activeTarget = { note_id: null, create_new_pending: true };
  writeAppState();
  try {
    await pythonRequest('POST', '/target', body);
  } catch (err) {
    console.error('[Picker] create-new POST failed:', err.message);
  }
  hidePicker();
});

// Phase 4: materialize an empty note RIGHT NOW (vs. create-new which only
// flags the routing target). Then pin the bubble to it and ask the main
// window to open it in edit mode.
ipcMain.handle('picker:create-empty-note', async () => {
  let newNote;
  try {
    newNote = await pythonRequest('POST', '/notes', {
      title: 'Untitled Note',
      content: '',
    });
  } catch (err) {
    console.error('[Picker] create-empty-note POST failed:', err.message);
    return null;
  }
  if (!newNote?.id) {
    return null;
  }
  // Pin routing target to this fresh note so the next capture appends to it.
  appState.activeTarget = { note_id: newNote.id, create_new_pending: false };
  writeAppState();
  try {
    await pythonRequest('POST', '/target', {
      note_id: newNote.id,
      create_new_pending: false,
    });
  } catch (err) {
    console.error('[Picker] set-target after create-empty-note failed:', err.message);
  }
  hidePicker();
  // Surface the main window and open the new note in edit mode.
  if (mainWindow) {
    if (!mainWindow.isVisible()) mainWindow.show();
    mainWindow.focus();
    mainWindow.webContents.send('note:open', newNote.id);
  }
  return newNote;
});

// ── Language picker IPC ─────────────────────────────────────────────────
ipcMain.handle('lang-picker:open', () => {
  showLangPicker();
});

ipcMain.handle('lang-picker:close', () => {
  hideLangPicker();
});

ipcMain.handle('lang-picker:get', async () => {
  // Source of truth: Python. Falls back to persisted appState if Python
  // is mid-restart so the picker can still render an active row.
  try {
    return await pythonRequest('GET', '/language', null);
  } catch (err) {
    return appState.outputLanguage || { code: 'auto', label: 'Global', emoji: '🌍' };
  }
});

ipcMain.handle('lang-picker:select', async (_e, payload) => {
  const lang = {
    code: payload?.code || 'auto',
    label: payload?.label || 'Global',
    emoji: payload?.emoji || '🌍',
  };
  appState.outputLanguage = lang;
  writeAppState();
  try {
    await pythonRequest('POST', '/language', lang);
  } catch (err) {
    console.error('[Lang Picker] select POST failed:', err.message);
  }
  hideLangPicker();
});
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
  // setBounds re-asserts the locked size on every move so Chromium's
  // fractional-DPI rounding on Windows can't silently grow the HWND.
  bubbleWindow.setBounds({
    x: Math.round(x + dx),
    y: Math.round(y + dy),
    width: BUBBLE_WINDOW_W,
    height: BUBBLE_WINDOW_H,
  });
});

app.whenReady().then(() => {
  if (isDev) {
    // Lazy require — the package touches Electron internals that aren't
    // available before whenReady fires. Installs once into the userData
    // directory; subsequent dev launches are no-ops.
    try {
      const installer = require('electron-devtools-installer');
      const { default: install, REACT_DEVELOPER_TOOLS } = installer;
      install(REACT_DEVELOPER_TOOLS)
        .then((name) => debug.log('DevTools', 'installed', name))
        .catch((err) => debug.warn('DevTools', 'install failed', err.message));
    } catch (err) {
      debug.warn('DevTools', 'installer not available', err.message);
    }
  }

  appState = readAppState();
  if (typeof appState.bubbleVisible !== 'boolean') appState.bubbleVisible = true;
  if (!appState.activeTarget || typeof appState.activeTarget !== 'object') {
    appState.activeTarget = { note_id: null, create_new_pending: false };
  }
  if (!appState.outputLanguage || typeof appState.outputLanguage !== 'object') {
    appState.outputLanguage = { code: 'auto', label: 'Global', emoji: '🌍' };
  }
  bubbleVisible = appState.bubbleVisible;

  createWindow();
  if (isDev) {
    // F12 toggles DevTools on the currently-focused window. Cheap, predictable.
    globalShortcut.register('F12', () => {
      const w = BrowserWindow.getFocusedWindow();
      if (w) w.webContents.toggleDevTools();
    });
  }
  createBubbleWindow();
  createTray();
  registerGlobalShortcut();
  startPythonService();
  // Re-assert persisted target to Python once it's listening. Retries
  // internally to absorb the few seconds of Python startup.
  restoreTargetToPython();
  // Same retry approach for the output-language preference.
  restoreLanguageToPython();
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
