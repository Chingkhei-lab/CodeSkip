/**
 * Preload Script - Secure Bridge between Renderer and Main Process
 * 
 * This script runs in a privileged context and exposes only specific
 * safe APIs to the renderer process through contextBridge.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Whitelist of valid channels for security
const VALID_SEND_CHANNELS = [
  'log',
  'set-click-through',
  'expand-overlay',
  'close-result-window',
  'ai-response'
];

const VALID_RECEIVE_CHANNELS = [
  'screenshot',
  'solve',
  'start-over',
  'scroll-ai-result',
  'set-transparency',
  'stealth-mode-changed',
  'toggle-main-window',
  'request-initial-state',
  'result-data',
  'render-result'
];

// Expose protected methods that allow the renderer process to use
// ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electron', {
  // Send messages to main process
  send: (channel, data) => {
    if (VALID_SEND_CHANNELS.includes(channel)) {
      ipcRenderer.send(channel, data);
    } else {
      console.error(`Attempt to send on invalid channel: ${channel}`);
    }
  },
  
  // Receive messages from main process (one-time listener)
  receive: (channel, func) => {
    if (VALID_RECEIVE_CHANNELS.includes(channel)) {
      // Strip event as it includes `sender` which could be abused
      ipcRenderer.on(channel, (event, ...args) => func(...args));
    } else {
      console.error(`Attempt to receive on invalid channel: ${channel}`);
    }
  },
  
  // Receive messages from main process (remove listener after first call)
  receiveOnce: (channel, func) => {
    if (VALID_RECEIVE_CHANNELS.includes(channel)) {
      ipcRenderer.once(channel, (event, ...args) => func(...args));
    } else {
      console.error(`Attempt to receiveOnce on invalid channel: ${channel}`);
    }
  },
  
  // Remove specific listener
  removeListener: (channel, func) => {
    if (VALID_RECEIVE_CHANNELS.includes(channel)) {
      ipcRenderer.removeListener(channel, func);
    }
  },
  
  // Remove all listeners for a channel
  removeAllListeners: (channel) => {
    if (VALID_RECEIVE_CHANNELS.includes(channel)) {
      ipcRenderer.removeAllListeners(channel);
    }
  },
  
  // Invoke (request-response pattern)
  invoke: async (channel, data) => {
    const VALID_INVOKE_CHANNELS = ['get-mobile-qr'];
    if (VALID_INVOKE_CHANNELS.includes(channel)) {
      return await ipcRenderer.invoke(channel, data);
    } else {
      console.error(`Attempt to invoke invalid channel: ${channel}`);
      throw new Error('Invalid IPC channel');
    }
  }
});

// Expose environment info (read-only)
contextBridge.exposeInMainWorld('electronEnv', {
  isElectron: true,
  platform: process.platform,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  }
});

console.log('✓ Preload script loaded - Secure IPC bridge established');