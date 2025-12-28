const { app, BrowserWindow, globalShortcut, ipcMain, screen, session, Tray, Menu, nativeImage } = require('electron');
const fs = require('fs');
const path = require('path');

console.log('===== ELECTRON STARTING =====');



// Create a log stream
const logStream = fs.createWriteStream(path.join(__dirname, 'electron.log'), { flags: 'a' });

// Preserve original console methods
const originalConsoleLog = console.log.bind(console);
const originalConsoleError = console.error.bind(console);

// Mirror console logs to file and original console, support multiple args/objects
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
    logStream.write(line + '\n');
  } catch {}
  originalConsoleError(...args);
};
console.log('  Loading modules...');

// Reduce transparency flicker on Windows by disabling GPU compositing
// Ensure hardware acceleration is enabled; disabling can make transparent windows invisible on Windows
try {
  if (app.isReady()) {
    // No-op; Electron uses hardware acceleration by default
  }
} catch {}

// Load custom modules with error handling
let graphicsHook, platformDetector, errorHandler, mobileCompanion;

try {
  graphicsHook = require(path.join(__dirname, '../../shared/graphics_hook'));
  console.log('  Γ£ô Graphics hook module loaded');
} catch (error) {
  console.log('  Γ£ù Failed to load graphics hook:');
  console.error(error);
  graphicsHook = {
    initialize: async () => console.warn('Graphics hook not available, running in basic mode.'),
    isHooked: () => false,
  };
}

try {
  platformDetector = require(path.join(__dirname, '../../shared/platform_detector'));
  console.log('  Γ£ô Platform detector module loaded');
} catch (error) {
  console.log('  Γ£ù Failed to load platform detector:');
  console.error(error);
  platformDetector = {
    startDetection: () => console.warn('Platform detector not available.'),
  };
}

try {
  errorHandler = require(path.join(__dirname, '../../shared/error_handler'));
  console.log('  Γ£ô Error handler module loaded');
} catch (error) {
  console.log('  Γ£ù Failed to load error handler:');
  console.error(error);
  errorHandler = {
    initializeWithApp: () => console.warn('Error handler not available.'),
    handleError: (type, error) => console.error(`Unhandled error (${type}):`, error),
  };
}

try {
  mobileCompanion = require(path.join(__dirname, '../../mobile/companion'));
  console.log('  Γ£ô Mobile companion module loaded');
} catch (error) {
  console.log('  Γ£ù Failed to load mobile companion:');
  console.error(error);
  mobileCompanion = {
    initialize: () => console.warn('Mobile companion not available.'),
    sendMessage: () => console.warn('Mobile companion not available.'),
    getQRCode: () => Promise.resolve({ error: 'Mobile companion not available' }),
  };
}

// Optional Windows-native capture hardening via SetWindowDisplayAffinity
let winAffinity;
try {
  if (process.platform === 'win32') {
    const ffi = require('ffi-napi');
    const ref = require('ref-napi');
    winAffinity = ffi.Library('user32', {
      SetWindowDisplayAffinity: ['bool', ['pointer', 'uint']]
    });
    console.log('  Γ£ô Native affinity library loaded');
  }
} catch (e) {
  console.log('  Γ£ù Native affinity unavailable; using Electron content protection only');
  winAffinity = null;
}

// Keep a global reference of the window objects
let mainWindow;
let overlayWindow;
let tray;

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
    tray.setToolTip('Ultracode Overlay');
    const menu = Menu.buildFromTemplate([
      {
        label: 'Show Overlay',
        click: () => { if (overlayWindow) { overlayWindow.show(); } }
      },
      {
        label: 'Hide Overlay',
        click: () => { if (overlayWindow) { overlayWindow.hide(); } }
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
            expandOverlay();                 // expand first
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
          if (overlayWindow.isVisible()) overlayWindow.hide(); else overlayWindow.show();
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
    // Create the browser window
    mainWindow = new BrowserWindow({
      width: 800,
      height: 600,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        enableRemoteModule: true,
      },
      icon: path.join(__dirname, 'icon.png'),
    });

    console.log('Main window object created');

    // Load the index.html from React app
    const startUrl = process.env.ELECTRON_START_URL || 'http://localhost:3000';
    console.log('Loading URL:', startUrl);
    
    mainWindow.loadURL(startUrl);

    // Open DevTools in development mode
    if (process.env.NODE_ENV === 'development' || !app.isPackaged) {
      mainWindow.webContents.openDevTools();
    }

    // Handle window events
    mainWindow.webContents.on('did-finish-load', () => {
      console.log('✓ Main window loaded successfully');
    });

    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      console.error('✗ Main window failed to load');
      errorHandler.handleError('ERR_WINDOW_LOAD', { errorCode, errorDescription });
    });

    mainWindow.on('closed', () => {
      console.log('Main window closed');
      mainWindow = null;
    });

    console.log('✓ Main window setup complete');
  } catch (error) {
    console.error('✗ Error creating main window:', error);
    errorHandler.handleError('ERR_WINDOW_CREATION', error);
  }
}

function createOverlayWindow() {
  console.log('===== CREATING OVERLAY WINDOW =====');
  
  try {
    const primary = screen.getPrimaryDisplay();
    const { width, height } = primary.workAreaSize;
    // PILL size (collapsed) – user cannot resize
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
      resizable: false,          // LOCK user resize
      minimizable: false,
      maximizable: false,
      titleBarStyle: 'hidden',
      backgroundColor: '#00000000', // Fully transparent
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        backgroundThrottling: false,
        devTools: false,
        sandbox: false,
        webSecurity: false,
        allowRunningInsecureContent: true,
      },
    });

    console.log('  Overlay window object created');

    // Ensure overlay is invisible in screenshots and screen sharing,
    // while remaining visible locally to the user.
    try {
      overlayWindow.setContentProtection(true);
      console.log('  ✓ Content protection enabled on overlay window');
    } catch (e) {
      console.warn('  ⚠ Failed to enable content protection', e);
    }

    // Windows-native capture hardening (optional): WDA_EXCLUDEFROMCAPTURE (0x00000011)
    try {
      if (process.platform === 'win32' && winAffinity) {
        const hwndBuf = overlayWindow.getNativeWindowHandle();
        const hwndPtr = hwndBuf && hwndBuf.buffer ? hwndBuf.buffer : hwndBuf; // Electron versions vary
        const WDA_EXCLUDEFROMCAPTURE = 0x00000011;
        const ok = winAffinity.SetWindowDisplayAffinity(hwndPtr, WDA_EXCLUDEFROMCAPTURE);
        console.log(`  ✓ SetWindowDisplayAffinity applied: ${ok ? 'OK' : 'FAILED'}`);
      }
    } catch (e) {
      console.warn('  ⚠ Native display affinity not applied; continuing with content protection', e);
    }

    const overlayUrl = path.join(__dirname, 'overlay.html');
    console.log('  Loading overlay URL:', overlayUrl);
    
    overlayWindow.loadFile(overlayUrl);
    // Enhanced behavior: selective click-through on transparent areas
    try {
      overlayWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
      overlayWindow.setFullScreenable(false);
      // Allow clicks to pass through transparent areas, keep interactive elements clickable
      overlayWindow.setIgnoreMouseEvents(true, { forward: true });
      overlayWindow.setOpacity(1.0);
    } catch {}

    overlayWindow.on('ready-to-show', () => {
      try {
        if (!app.isPackaged) {
          overlayWindow.show();
          overlayWindow.focus();
          console.log('Overlay ready; compact and interactable in development');
        } else {
          console.log('Overlay ready but remaining hidden for stealth');
        }
      } catch (e) {
        console.error('Failed in ready-to-show handler', e);
      }
    });
    overlayWindow.webContents.on('did-finish-load', () => {
      console.log('  Γ£ô Overlay window loaded successfully');
      // Expand window so navbar is visible on startup
      try {
        expandOverlay();
        // Re-assert content protection post-load (defensive, no-op if already set)
        try { overlayWindow.setContentProtection(true); } catch {}
        // Re-assert affinity post-load
        try {
          if (process.platform === 'win32' && winAffinity) {
            const hwndBuf = overlayWindow.getNativeWindowHandle();
            const hwndPtr = hwndBuf && hwndBuf.buffer ? hwndBuf.buffer : hwndBuf;
            const WDA_EXCLUDEFROMCAPTURE = 0x00000011;
            winAffinity.SetWindowDisplayAffinity(hwndPtr, WDA_EXCLUDEFROMCAPTURE);
          }
        } catch {}
      } catch (e) {
        console.error('Failed to expand overlay on load', e);
      }
    });

    overlayWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
      console.log('  Γ£ù Overlay window failed to load');
      errorHandler.handleError('ERR_OVERLAY_LOAD', { errorCode, errorDescription });
    });

    overlayWindow.on('closed', () => {
      console.log('Overlay window closed');
      overlayWindow = null;
    });

    console.log('  Γ£ô Overlay window setup complete');
  } catch (error) {
    console.log('  Γ£ù Error creating overlay window:');
    console.error(error);
    errorHandler.handleError('ERR_OVERLAY_CREATION', error);
  }
}

// Create windows when Electron is ready
app.whenReady().then(async () => {
  console.log('===== APP IS READY =====');
  
  // Privacy & security enhancements
  try {
    session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
      const blockedDomains = [
        'google-analytics.com',
        'doubleclick.net',
        'facebook.com/tr',
        'segment.com',
        'mixpanel.com'
      ];
      const shouldBlock = blockedDomains.some(domain => details.url.includes(domain));
      callback({ cancel: shouldBlock });
    });
    session.defaultSession.cookies.flushStore().then(() => {
      session.defaultSession.clearStorageData();
    });
  } catch {}

  // Initialize error handler with app
  errorHandler.initializeWithApp(app);
  
  createOverlayWindow();
  // Optionally show the React control panel:
  // createMainWindow();

  // Initialize graphics hook
  try {
    await graphicsHook.initialize();
    if (graphicsHook && typeof graphicsHook.installHook === 'function') {
      graphicsHook.installHook();
    } else {
      console.log('Graphics hook not available, running in basic mode.');
    }
  } catch (error) {
    console.log('  Γ£ù Failed to initialize graphics hook:');
    console.error(error);
    console.log('Graphics hook not available, running in basic mode.');
  }

  // Start platform detection
  platformDetector.startDetection(overlayWindow, (platform) => {
    if (platform) {
      console.log(`  Γ£ô Detected platform: ${platform.name}`);
    } else {
      console.log('No specific platform detected');
    }
  });
  
  // Initialize mobile companion mode
  mobileCompanion.initialize();

  // Register global shortcuts
  try {
    const regs = [];
    regs.push({ combo: 'CommandOrControl+Shift+Space', ok: globalShortcut.register('CommandOrControl+Shift+Space', () => {
      if (overlayWindow) {
        if (overlayWindow.isVisible()) { overlayWindow.hide(); console.log('Overlay hidden'); }
        else { overlayWindow.show(); console.log('Overlay shown'); }
      }
    }) });

    regs.push({ combo: 'CommandOrControl+Shift+S', ok: globalShortcut.register('CommandOrControl+Shift+S', () => {
      if (overlayWindow) {
        const isIgnoring = overlayWindow.isIgnoringMouseEvents();
        if (!isIgnoring) {
          overlayWindow.setIgnoreMouseEvents(true, { forward: true });
          console.log('Overlay click-through: ON (forward)');
        } else {
          overlayWindow.setIgnoreMouseEvents(false);
          console.log('Overlay click-through: OFF');
        }
      }
    }) });

    regs.push({ combo: 'CommandOrControl+Shift+R', ok: globalShortcut.register('CommandOrControl+Shift+R', () => {
      if (overlayWindow) overlayWindow.webContents.send('start-over');
    }) });

    regs.push({ combo: 'CommandOrControl+Shift+E', ok: globalShortcut.register('CommandOrControl+Shift+E', () => {
      if (overlayWindow) {
        console.log('Shortcut: Solve triggered');
        expandOverlay();                 // expand first
        overlayWindow.webContents.send('solve');
      }
    }) });

    regs.push({ combo: 'CommandOrControl+Shift+C', ok: globalShortcut.register('CommandOrControl+Shift+C', () => {
      if (overlayWindow) {
        console.log('Shortcut: Screenshot triggered');
        overlayWindow.webContents.send('screenshot');
      }
    }) });

    // Scroll solution panel shortcuts
    regs.push({ combo: 'CommandOrControl+Shift+Up', ok: globalShortcut.register('CommandOrControl+Shift+Up', () => {
      if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', -120);
    }) });
    regs.push({ combo: 'CommandOrControl+Shift+Down', ok: globalShortcut.register('CommandOrControl+Shift+Down', () => {
      if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', 120);
    }) });

    // Register movement shortcuts (25px step)
    const step = 25;
    regs.push({ combo: 'CommandOrControl+Up', ok: globalShortcut.register('CommandOrControl+Up', () => moveOverlay(0, -step)) });
    regs.push({ combo: 'CommandOrControl+Down', ok: globalShortcut.register('CommandOrControl+Down', () => moveOverlay(0, step)) });
    regs.push({ combo: 'CommandOrControl+Left', ok: globalShortcut.register('CommandOrControl+Left', () => moveOverlay(-step, 0)) });
    regs.push({ combo: 'CommandOrControl+Right', ok: globalShortcut.register('CommandOrControl+Right', () => moveOverlay(step, 0)) });

    // Fallback alternatives if any registration failed
    if (!regs.every(r => r.ok)) {
      console.log('Some shortcuts failed; registering fallbacks');
      globalShortcut.register('Alt+Shift+E', () => { if (overlayWindow) overlayWindow.webContents.send('solve'); });
      globalShortcut.register('Alt+Shift+C', () => { if (overlayWindow) overlayWindow.webContents.send('screenshot'); });
      globalShortcut.register('Alt+Shift+Up', () => { if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', -120); });
      globalShortcut.register('Alt+Shift+Down', () => { if (overlayWindow) overlayWindow.webContents.send('scroll-ai-result', 120); });
      globalShortcut.register('Alt+Shift+Space', () => {
        if (overlayWindow) {
          if (overlayWindow.isVisible()) overlayWindow.hide(); else overlayWindow.show();
        }
      });
    }
    regs.forEach(r => console.log(`Shortcut ${r.combo}: ${r.ok ? 'OK' : 'FAILED'}`));
    console.log('✓ Global shortcuts registration attempted with fallbacks');
  } catch (error) {
    console.error('✗ Failed to register shortcuts:', error);
  }

  console.log('===== INITIALIZATION COMPLETE =====');
  // Initialize tray last so it reflects current window state
  createTray();
});

// Further minimize detectable properties when ready
app.on('ready', () => {
  try {
    if (overlayWindow) {
      overlayWindow.setTitle('');
      overlayWindow.setAccessibilitySupportEnabled(false);
    }
    if (app.isPackaged) {
      app.setName('System Helper');
      process.title = 'System Helper Process';
    }
  } catch {}
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  console.log('All windows closed');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  console.log('App activated');
  if (mainWindow === null) {
    createMainWindow();
  }
  if (overlayWindow === null) {
    createOverlayWindow();
  }
});

// Clean up global shortcuts
app.on('will-quit', () => {
  console.log('App will quit, cleaning up...');
  globalShortcut.unregisterAll();
});

// IPC handlers
ipcMain.on('toggle-overlay', (event, isVisible) => {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    if (isVisible) {
      overlayWindow.show();
    } else {
      overlayWindow.hide();
    }
  }
});

// Overlay log passthrough for comprehensive terminal logging
ipcMain.on('log', (event, message) => {
  try {
    console.log(`[OVERLAY] ${message}`);
  } catch (e) {
    console.error('Failed to log overlay message', e);
  }
});

// Allow overlay to explicitly set click-through state
ipcMain.on('set-click-through', (event, enabled) => {
  try {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
      overlayWindow.setIgnoreMouseEvents(!!enabled);
      console.log(`Overlay click-through set to: ${enabled ? 'ON' : 'OFF'}`);
    }
  } catch (e) {
    console.error('Failed to set click-through', e);
  }
});

// Allow renderer to request overlay expansion explicitly
ipcMain.on('expand-overlay', () => {
  try {
    expandOverlay();
  } catch (e) {
    console.error('Failed to expand overlay via IPC', e);
  }
});

// Expand overlay to working size when Solve is triggered
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

  // Movement helpers
function clampBounds(bounds) {
  // Allow overlay to move off-screen while keeping a 10px handle visible
  const wa = screen.getPrimaryDisplay().workArea;
  const minX = wa.x - bounds.width + 1;
  const maxX = wa.x + wa.width - 1;
  const minY = wa.y - bounds.height + 1;
  const maxY = wa.y + wa.height - 1;
  bounds.x = Math.min(Math.max(bounds.x, minX), maxX);
  bounds.y = Math.min(Math.max(bounds.y, minY), maxY);
  return bounds;
}

// Transparency controls via keyboard shortcuts
function registerTransparencyShortcuts() {
  try {
    const send = (payload) => {
      if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.webContents.send('set-transparency', payload);
      }
    };
    // Increase transparency (less opaque)
    const incKeys = [
      'CommandOrControl+Shift+=',
      'CommandOrControl+=',
      'Alt+Shift+=',
    ];
    // Decrease transparency (more opaque)
    const decKeys = [
      'CommandOrControl+Shift+-',
      'CommandOrControl+-',
      'Alt+Shift+-',
    ];
    incKeys.forEach(k => globalShortcut.register(k, () => send({ action: 'inc' })));
    decKeys.forEach(k => globalShortcut.register(k, () => send({ action: 'dec' })));
    // Reset to default
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

// Handle AI response messages: forward to mobile companion and open results window
let resultsWindow;
function openResultsWindow(content) {
  try {
    if (!resultsWindow || resultsWindow.isDestroyed()) {
      const { width, height } = screen.getPrimaryDisplay().workAreaSize;
      resultsWindow = new BrowserWindow({
        width: 900,
        height: 650,
        x: Math.round((width - 900) / 2),
        y: Math.round((height - 650) / 2),
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        skipTaskbar: true,          // same as overlay
        resizable: true,
        show: false,                // hide until ready (prevents flash)
        webPreferences: {
          nodeIntegration: true,
          contextIsolation: false,
        },
        icon: path.join(__dirname, 'icon.png'),
        title: 'AI Result'
      });
      resultsWindow.on('closed', () => { resultsWindow = null; });
      const resultUrl = path.join(__dirname, 'result.html');
      resultsWindow.loadFile(resultUrl);
      resultsWindow.webContents.once('dom-ready', () => {
        resultsWindow.show();
        resultsWindow.webContents.send('result-data', { content });
      });
    } else {
      resultsWindow.focus();
      resultsWindow.webContents.send('render-result', content);
    }
  } catch (error) {
    console.error('Failed to open results window', error);
    errorHandler.handleError('ERR_RESULTS_WINDOW', error);
  }
}

ipcMain.on('close-result-window', () => {
  if (resultsWindow && !resultsWindow.isDestroyed()) {
    resultsWindow.close();
  }
});

ipcMain.on('ai-response', (event, message) => {
  mobileCompanion.sendMessage({
    role: 'ai',
    content: message.content,
    timestamp: new Date().toISOString()
  });
  // Rendering now handled inline in overlay; do not open separate window
});

// Get mobile companion QR code
ipcMain.handle('get-mobile-qr', async () => {
  return await mobileCompanion.getQRCode();
});

console.log('===== ELECTRON SCRIPT LOADED =====');
// Detection avoidance command-line switches
try {
  app.commandLine.appendSwitch('disable-site-isolation-trials');
  app.commandLine.appendSwitch('disable-features', 'OutOfBlinkCors');
  if (process.platform === 'win32') {
    app.commandLine.appendSwitch('windows-disable-version-compat-checks');
  }
} catch {}
  // Register transparency control shortcuts
  registerTransparencyShortcuts();