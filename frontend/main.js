'use strict';

const { app, BrowserWindow, ipcMain, net } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const WebSocket = require('ws');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const DEFAULT_PORT = 8765;
let backendPort = DEFAULT_PORT;
const WS_RECONNECT_DELAY_MS = 2000;

let pythonProcess = null;
let ws = null;
let overlayWindow = null;
let settingsWindow = null;

// ---------------------------------------------------------------------------
// Backend executable path
// ---------------------------------------------------------------------------

function getBackendArgs() {
  if (app.isPackaged) {
    const ext = process.platform === 'win32' ? '.exe' : '';
    const exe = path.join(process.resourcesPath, 'backend', `main${ext}`);
    return { exe, args: [`--port=${backendPort}`] };
  }
  // Development: run Python directly
  const script = path.join(__dirname, '..', 'backend', 'main.py');
  return { exe: process.platform === 'win32' ? 'python' : 'python3', args: [script, `--port=${backendPort}`] };
}

// ---------------------------------------------------------------------------
// Backend lifecycle
// ---------------------------------------------------------------------------

async function startBackend() {
  backendPort = await findFreePort(DEFAULT_PORT);
  const { exe, args } = getBackendArgs();

  pythonProcess = spawn(exe, args, { stdio: ['ignore', 'pipe', 'pipe'] });
  pythonProcess.stdout.on('data', (d) => process.stdout.write(`[backend] ${d}`));
  pythonProcess.stderr.on('data', (d) => process.stderr.write(`[backend:err] ${d}`));
  pythonProcess.on('exit', (code) => {
    console.log(`Backend exited (code ${code})`);
    pythonProcess = null;
  });

  await waitForBackend(backendPort);
}

function findFreePort(startPort) {
  return new Promise((resolve) => {
    const { createServer } = require('net');
    let port = startPort;
    const tryPort = () => {
      const srv = createServer();
      srv.listen(port, '127.0.0.1', () => {
        srv.close(() => resolve(port));
      });
      srv.on('error', () => {
        port++;
        if (port > startPort + 20) resolve(startPort); // fallback
        else tryPort();
      });
    };
    tryPort();
  });
}

function waitForBackend(port, retries = 40, delayMs = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const check = () => {
      const req = net.request({ method: 'GET', url: `http://127.0.0.1:${port}/api/status` });
      req.on('response', (res) => {
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on('error', retry);
      req.end();
    };
    const retry = () => {
      if (++attempts >= retries) return reject(new Error('Backend did not start in time'));
      setTimeout(check, delayMs);
    };
    check();
  });
}

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createOverlayWindow() {
  overlayWindow = new BrowserWindow({
    width: 440,
    height: 360,
    minWidth: 320,
    minHeight: 200,
    alwaysOnTop: true,
    frame: false,
    transparent: process.platform !== 'linux',
    backgroundColor: process.platform === 'linux' ? '#0f0f14' : undefined,
    resizable: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  overlayWindow.loadFile(path.join(__dirname, 'renderer', 'overlay', 'index.html'));

  // Stay visible over fullscreen apps on macOS
  if (process.platform === 'darwin') {
    overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  }

  overlayWindow.on('closed', () => { overlayWindow = null; });
}

function createSettingsWindow() {
  settingsWindow = new BrowserWindow({
    width: 620,
    height: 680,
    show: false,
    parent: overlayWindow || undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  settingsWindow.loadFile(path.join(__dirname, 'renderer', 'settings', 'settings.html'));
  settingsWindow.on('close', (e) => { e.preventDefault(); settingsWindow.hide(); });
}

// ---------------------------------------------------------------------------
// WebSocket client
// ---------------------------------------------------------------------------

function connectWebSocket() {
  const url = `ws://127.0.0.1:${backendPort}/ws`;
  ws = new WebSocket(url);

  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    // Forward to both windows
    for (const win of [overlayWindow, settingsWindow]) {
      if (win && !win.isDestroyed()) {
        win.webContents.send(msg.type, msg);
      }
    }
  });

  ws.on('close', () => {
    ws = null;
    setTimeout(connectWebSocket, WS_RECONNECT_DELAY_MS);
  });

  ws.on('error', () => {
    // close event will trigger reconnect
  });
}

// ---------------------------------------------------------------------------
// Backend REST helper
// ---------------------------------------------------------------------------

function backendFetch(path_, method = 'GET', body = null) {
  return new Promise((resolve, reject) => {
    const req = net.request({
      method,
      url: `http://127.0.0.1:${backendPort}${path_}`,
    });
    req.setHeader('Content-Type', 'application/json');
    if (body) req.write(JSON.stringify(body));

    let data = '';
    req.on('response', (res) => {
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch { resolve({}); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

// ---------------------------------------------------------------------------
// IPC handlers
// ---------------------------------------------------------------------------

ipcMain.handle('get-config',        () => backendFetch('/api/config'));
ipcMain.handle('save-config', (_, c) => backendFetch('/api/config', 'POST', c));
ipcMain.handle('get-devices',        () => backendFetch('/api/devices'));
ipcMain.handle('get-ollama-models',  () => backendFetch('/api/ollama/models'));
ipcMain.handle('start-capture',      () => backendFetch('/api/start', 'POST'));
ipcMain.handle('stop-capture',       () => backendFetch('/api/stop', 'POST'));
ipcMain.handle('trigger-manual',     () => backendFetch('/api/trigger', 'POST'));
ipcMain.handle('get-status',         () => backendFetch('/api/status'));

ipcMain.on('open-settings', () => {
  if (settingsWindow) settingsWindow.show();
});
ipcMain.on('close-settings', () => {
  if (settingsWindow) settingsWindow.hide();
});

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  try {
    await startBackend();
  } catch (err) {
    console.error('Failed to start backend:', err);
    // Continue anyway — user may start it manually
  }

  createOverlayWindow();
  createSettingsWindow();
  connectWebSocket();

  app.on('activate', () => {
    if (!overlayWindow) createOverlayWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
});
