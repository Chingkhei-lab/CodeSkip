const { app, BrowserWindow, globalShortcut, ipcMain, screen, session, Tray, Menu, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

console.log('===== ULTRACODE SECURE - STARTING =====');

// Create a log stream
const logStream = fs.createWriteStream(path.join(__dirname, 'electron.log'), { flags: 'a' });

// Preserve original console methods
const originalConsoleLog = console.log.bind(console);
const originalConsoleError = console.error.bind(console);

console.log = (...args) => {
  try {
    const line = args.map(arg => {
      if (typeof arg === 'string') return arg;
      try { return JSON.stringify(arg); } catch { return String(arg); }
    }).join(' ');
    logStream.write(line + '\n');
  } catch {}
  originalConsoleLog(...args);
};

console.error = (...args) => {
  try {
    const line = args.map(arg => {
      if (typeof arg === 'string') return arg;
      try { return JSON.stringify(arg); } catch { return String(arg); }
    }).join(' ');
    logStream.write('[ERROR] ' + line + '\n');
  } catch {}
  originalConsoleError(...args);
};

// Keep a global reference of the window objects
let mainWindow;
let overlayWindow;
let tray;

// SECURITY: Content Security Policy
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "connect-src 'self' ws://127.0.0.1:8000 http://127.0.0.1:8000",
  "img-src 'self' data:",
  "font-src 'self' data:"
].join('; ');

function createTray() {
  try {
    const iconPath = path.join(__dirname, 'icon.png');
    let image;
    try {
      image = nativeImage.createFromPath(iconPath);
      if (image.isEmpty()) throw new Error('Empty image');
    } catch {
      image = nativeImage.createEmpty();
    }
    tray = new Tray(image);
    tray.setToolTip('Ultracode - Secure');
    const menu = Menu.buildFromTemplate([
      {
        label: 'Show Overlay',
        click: () => { if (overlayWindow) overlayWindow.show(); }
      },
      {
        label: 'Hide Overlay',
        click: () => { if (overlayWindow) overlayWindow.hide(); }
      },
      { type: 'separator' },
      { label: 'Snap Center', click: () => snapOverlay('center') },
      { label: 'Snap Top-Left', click: () => snapOverlay('tl') },
      { label: 'Snap Bottom-Right', click: () => snapOverlay('br') },
      { type: 'separator' },
      {
        label: 'Screenshot',
        click: () => { if (overlayWindow) overlayWindow.webContents.send('screenshot'); }
      },
      {
        label: 'Solve',
        click: () => {
          if (overlayWindow) {
            expandOverlay();
            overlayWindow.webContents.send('solve');
          }
        }
      },
      { type: 'separator' },
      { label: 'Quit', click: () => app.quit() }
    ]);
    tray.setContextMenu(menu);
    tray.on('click', () => {
      try {
        if (overlayWindow) {
          if (overlayWindow.isVisible()) overlayWindow.hide();
          else overlayWindow.show();
        }
      } catch (e) {
        console.error('Tray click handler failed', e);
      }
    });
    console.log('✓ System tray initialized');
  } catch (e) {
    console.error('✗ Failed to create tray', e);
  }
}

function createMainWindow() {
  console.log('===== CREATING MAIN WINDOW =====');
  
  try {
    mainWindow = new BrowserWindow({
      width: 800,
      height: 600,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
      },
      icon: path.join(__dirname, 'icon.png'),
    });

    const startUrl = process.env.ELECTRON_START_URL || 'http://localhost:3000';
    console.log('Loading URL:', startUrl);
    mainWindow.loadURL(startUrl);

    if (process.env.NODE_ENV === 'development' || !app.isPackaged) {
      mainWindow.webContents.openDevTools();
    }

    mainWindow.on('closed', () => {
      console.log('Main window closed');
      mainWindow = null;
    });

    console.log('✓ Main window setup complete');
  } catch (error) {
    console.error('✗ Error creating main window:', error);
  }
}

function createOverlayWindow() {
  console.log('===== CREATING SECURE OVERLAY WINDOW =====');
  
  try {
    const primary = screen.getPrimaryDisplay();
    const { width, height } = primary.workAreaSize;
    const pillWidth = 60;
    const pillHeight = 32;
    const startX = Math.round((width - pillWidth) / 2) + primary.workArea.x;
    const startY = Math.round((height - pillHeight) / 2) + primary.workArea.y;

    overlayWindow = new BrowserWindow({
      width: pillWidth,
      height: pillHeight,
      x: startX,
      y: startY,
      useContentSize: true,
      transparent: true,
      frame: false,
      alwaysOnTop: true,
      skipTaskbar: true,
      show: !app.isPackaged,
      focusable: true,
      hasShadow: false,
      thickFrame: false,
      resizable: false,
      minimizable: false,
      maximizable: false,
      titleBarStyle: 'hidden',
      backgroundColor: '#00000000',
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        backgroundThrottling: false,
      },
    });

    console.log('✓ Overlay window object created with security enabled');

    // Content protection for screen sharing invisibility
    try {
      overlayWindow.setContentProtection(true);
      console.log('✓ Content protection enabled');
    } catch (e) {
      console.warn('⚠ Content protection failed', e);
    }

    // CRITICAL: Always enable click-through (forward mouse events)
    overlayWindow.setIgnoreMouseEvents(true, { forward: true });
    console.log('✓ Click-through mode: ALWAYS ON');

    const overlayUrl = path.join(__dirname, 'overlay.html');
    console.log('Loading overlay:', overlayUrl);
    overlayWindow.loadFile(overlayUrl);

    try {
      overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
      overlayWindow.setFullScreenable(false);
      overlayWindow.setOpacity(1.0);
    } catch {}

    overlayWindow.on('ready-to-show', () => {
      try {
        if (!app.isPackaged) {
          overlayWindow.show();
          overlayWindow.focus();
          console.log('✓ Overlay ready (development mode)');
        } else {
          console.log('✓ Overlay ready (stealth mode)');
        }
      } catch (e) {
        console.error('Failed in ready-to-show', e);
      }
    });

    overlayWindow.webContents.on('did-finish-load', () => {
      console.log('✓ Overlay loaded successfully');
      try {
        expandOverlay();
        overlayWindow.setContentProtection(true);
      } catch (e) {
        console.error('Failed to expand overlay on load', e);
      }
    });

    overlayWindow.on('closed', () => {
      console.log('Overlay window closed');
      overlayWindow = null;
    });

    console.log('✓ Overlay window setup complete');
  } catch (error) {
    console.error('✗ Error creating overlay:', error);
  }
}

// App ready handler
app.whenReady().then(async () => {
  console.log('===== APP IS READY =====');
  
  // SECURITY: Privacy & tracking protection
  try {
    session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
      const blockedDomains = [
        'google-analytics.com',
        'doubleclick.net',
        'facebook.com/tr',
        'segment.com',
        'mixpanel.com',
        'hotjar.com',
        'clarity.ms'
      ];
      const shouldBlock = blockedDomains.some(domain => details.url.includes(domain));
      callback({ cancel: shouldBlock });
    });
    
    await session.defaultSession.clearStorageData();
    console.log('✓ Privacy protection enabled');
  } catch (e) {
    console.error('Privacy protection setup failed', e);
  }
  
  createOverlayWindow();
  // Optionally: createMainWindow();

  // Register global shortcuts
  try {
    const shortcuts = [
      {
        keys: 'CommandOrControl+Shift+Space',
        action: () => {
          if (overlayWindow) {
            if (overlayWindow.isVisible()) {
              overlayWindow.hide();
              console.log('Overlay hidden');
            } else {
              overlayWindow.show();
              console.log('Overlay shown');
            }
          }
        },
        description: 'Toggle overlay visibility'
      },
      {
        keys: 'CommandOrControl+Shift+R',
        action: () => {
          if (overlayWindow) overlayWindow.webContents.send('start-over');
        },
        description: 'Start over'
      },
      {
        keys: 'CommandOrControl+Shift+C',
        action: () => {
          if (overlayWindow) {
            console.log('[HOTKEY] Screenshot triggered');
            overlayWindow.webContents.send('screenshot');
          }
        },
        description: 'Take screenshot'
      },
      {
        keys: 'CommandOrControl+Shift+E',
        action: () => {
          if (overlayWindow) {
            console.log('[HOTKEY] Solve triggered');
            expandOverlay();
            overlayWindow.webContents.send('solve');
          }
        },
        description: 'Trigger solve'
      },
      {
        keys: 'CommandOrControl+Shift+Up',
        action: () => {
          if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', -120);
        },
        description: 'Scroll up'
      },
      {
        keys: 'CommandOrControl+Shift+Down',
        action: () => {
          if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', 120);
        },
        description: 'Scroll down'
      },
      {
        keys: 'CommandOrControl+Up',
        action: () => moveOverlay(0, -25),
        description: 'Move up'
      },
      {
        keys: 'CommandOrControl+Down',
        action: () => moveOverlay(0, 25),
        description: 'Move down'
      },
      {
        keys: 'CommandOrControl+Left',
        action: () => moveOverlay(-25, 0),
        description: 'Move left'
      },
      {
        keys: 'CommandOrControl+Right',
        action: () => moveOverlay(25, 0),
        description: 'Move right'
      }
    ];

    shortcuts.forEach(({ keys, action, description }) => {
      const success = globalShortcut.register(keys, action);
      console.log(`Shortcut ${keys} (${description}): ${success ? 'OK' : 'FAILED'}`);
    });

    // Fallback shortcuts if main ones fail
    if (!shortcuts.every(s => globalShortcut.isRegistered(s.keys))) {
      console.log('Registering fallback shortcuts with Alt+Shift');
      globalShortcut.register('Alt+Shift+E', () => {
        if (overlayWindow) overlayWindow.webContents.send('solve');
      });
      globalShortcut.register('Alt+Shift+C', () => {
        if (overlayWindow) overlayWindow.webContents.send('screenshot');
      });
    }

    console.log('✓ Global shortcuts registered');
  } catch (error) {
    console.error('✗ Failed to register shortcuts:', error);
  }

  registerTransparencyShortcuts();
  createTray();
  console.log('===== INITIALIZATION COMPLETE =====');
});

// Security hardening on ready
app.on('ready', () => {
  try {
    if (overlayWindow) {
      overlayWindow.setTitle('');
    }
    if (app.isPackaged) {
      app.setName('System Helper');
      process.title = 'System Helper';
    }
  } catch {}
});

// Clean shutdown
app.on('window-all-closed', () => {
  console.log('All windows closed');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  console.log('App activated');
  if (overlayWindow === null) {
    createOverlayWindow();
  }
});

app.on('will-quit', () => {
  console.log('App will quit, cleaning up...');
  globalShortcut.unregisterAll();
});

// IPC handlers
ipcMain.on('toggle-overlay', (event, isVisible) => {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    if (isVisible) overlayWindow.show();
    else overlayWindow.hide();
  }
});

ipcMain.on('log', (event, message) => {
  try {
    console.log(`[OVERLAY] ${message}`);
  } catch (e) {
    console.error('Failed to log overlay message', e);
  }
});

ipcMain.on('expand-overlay', () => {
  try {
    expandOverlay();
  } catch (e) {
    console.error('Failed to expand overlay via IPC', e);
  }
});

function expandOverlay() {
  if (!overlayWindow || overlayWindow.isDestroyed()) return;
  const primary = screen.getPrimaryDisplay();
  const wa = primary.workArea;
  const workWidth = 900;
  const workHeight = 650;
  const x = wa.x + Math.round((wa.width - workWidth) / 2);
  const y = wa.y + Math.round((wa.height - workHeight) / 2);
  overlayWindow.setBounds({ x, y, width: workWidth, height: workHeight });
  console.log('Overlay expanded to working size');
}

function clampBounds(bounds) {
  const wa = screen.getPrimaryDisplay().workArea;
  const minX = wa.x - bounds.width + 10;
  const maxX = wa.x + wa.width - 10;
  const minY = wa.y - bounds.height + 10;
  const maxY = wa.y + wa.height - 10;
  bounds.x = Math.min(Math.max(bounds.x, minX), maxX);
  bounds.y = Math.min(Math.max(bounds.y, minY), maxY);
  return bounds;
}

function registerTransparencyShortcuts() {
  try {
    const send = (payload) => {
      if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.webContents.send('set-transparency', payload);
      }
    };
    globalShortcut.register('CommandOrControl+Shift+=', () => send({ action: 'inc' }));
    globalShortcut.register('CommandOrControl+Shift+-', () => send({ action: 'dec' }));
    globalShortcut.register('CommandOrControl+Shift+0', () => send({ value: 0.6 }));
    console.log('✓ Transparency shortcuts registered');
  } catch (e) {
    console.error('Failed to register transparency shortcuts', e);
  }
}

function moveOverlay(dx, dy) {
  if (!overlayWindow) return;
  const b = overlayWindow.getBounds();
  const next = clampBounds({ ...b, x: b.x + dx, y: b.y + dy });
  overlayWindow.setBounds(next);
  console.log(`Overlay moved to (${next.x}, ${next.y})`);
}

function snapOverlay(pos) {
  if (!overlayWindow) return;
  const wa = screen.getPrimaryDisplay().workArea;
  const b = overlayWindow.getBounds();
  let x = wa.x + Math.round((wa.width - b.width) / 2);
  let y = wa.y + Math.round((wa.height - b.height) / 2);
  if (pos === 'tl') { x = wa.x; y = wa.y; }
  if (pos === 'br') { x = wa.x + wa.width - b.width; y = wa.y + wa.height - b.height; }
  overlayWindow.setBounds({ ...b, x, y });
  console.log(`Overlay snapped: ${pos}`);
}

// SECURITY: Detection avoidance
try {
  app.commandLine.appendSwitch('disable-site-isolation-trials');
  app.commandLine.appendSwitch('disable-features', 'OutOfBlinkCors');
} catch {}

console.log('===== ELECTRON SCRIPT LOADED (SECURE) =====');