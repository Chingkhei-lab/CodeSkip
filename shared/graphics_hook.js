/**
 * Graphics Hook Module for Ultracode Clone
 * 
 * This module implements advanced screen-sharing invisibility by intercepting
 * the graphics pipeline before screen capture occurs.
 */

let psList;

class GraphicsHook {
  constructor() {
    this.isHooked = false;
    this.captureProcesses = [
        'obs64.exe',
        'obs32.exe',
        'xsplit.core.exe',
        'bandicam.exe',
        'fraps.exe',
        'camtasia.exe',
        'sharex.exe',
        'greenshot.exe',
        'lightshot.exe',
        'snippingtool.exe',
        'snipaste.exe',
        'picpick.exe',
        'faststonecapture.exe',
        'screentogif.exe',
        'licecap.exe',
        'gifcam.exe',
        'captura.exe',
        'streamlabs obs.exe',
        'nvidia shadowplay.exe',
        'amd relive.exe',
    ];
    this.platformHooks = {
      win32: this._setupWindowsHook,
      darwin: this._setupMacOSHook,
      linux: this._setupLinuxHook
    };
  }

  /**
   * Initialize the appropriate graphics hook based on platform
   */
  async initialize() {
    const { default: psListDefault } = await import('ps-list');
    psList = psListDefault;
    const platform = process.platform;
    
    console.log(`Initializing graphics hook for ${platform}...`);
    
    if (this.platformHooks[platform]) {
      try {
        this.platformHooks[platform].call(this);
        
        if (this.nativeLibraryAvailable) {
          console.log(`Graphics hook initialized for ${platform}`);
          return true;
        } else {
          console.warn(`Graphics hook native library not available for ${platform}`);
          console.warn('Running in fallback mode (basic overlay without advanced invisibility)');
          return false;
        }
      } catch (error) {
        console.error(`Failed to initialize graphics hook: ${error.message}`);
        console.warn('Running in fallback mode (basic overlay without advanced invisibility)');
        return false;
      }
    } else {
      console.error(`Unsupported platform: ${platform}`);
      return false;
    }
  }

  /**
   * Check if native library file exists
   */
  _checkNativeLibrary(libraryPath) {
    try {
      return fs.existsSync(libraryPath);
    } catch (error) {
      return false;
    }
  }

  /**
   * Set up Windows-specific screen capture detection
   */
  _setupWindowsHook() {
    this.nativeLibraryAvailable = true; // We'll use JS-based detection
  }

  /**
   * Set up macOS-specific CoreGraphics hooking
   */
  _setupMacOSHook() {
    try {
      // Path to the native dylib that implements the hook
      const dylibPath = path.join(__dirname, 'native', 'UltracodeHook.dylib');
      
      if (!this._checkNativeLibrary(dylibPath)) {
        console.warn(`Native library not found: ${dylibPath}`);
        console.warn('To enable advanced invisibility, you need to compile the native hook library.');
        this.nativeLibraryAvailable = false;
        return;
      }

      // Try to load FFI
      let ffi;
      try {
        ffi = require('ffi-napi');
      } catch (error) {
        console.warn('ffi-napi not installed. Run: npm install ffi-napi ref-napi');
        this.nativeLibraryAvailable = false;
        return;
      }
      
      this.hookLibrary = ffi.Library(dylibPath, {
        'InstallHook': ['bool', []],
        'RemoveHook': ['bool', []],
        'SetWindowHandle': ['bool', ['int']],
        'IsHookActive': ['bool', []]
      });
      
      this.nativeLibraryAvailable = true;
      this.isHooked = false;
    } catch (error) {
      console.error('Failed to load macOS hook library:', error.message);
      this.nativeLibraryAvailable = false;
    }
  }

  /**
   * Set up Linux-specific X11/Wayland hooking
   */
  _setupLinuxHook() {
    try {
      // Path to the native .so that implements the hook
      const soPath = path.join(__dirname, 'native', 'UltracodeHook.so');
      
      if (!this._checkNativeLibrary(soPath)) {
        console.warn(`Native library not found: ${soPath}`);
        console.warn('To enable advanced invisibility, you need to compile the native hook library.');
        this.nativeLibraryAvailable = false;
        return;
      }

      // Try to load FFI
      let ffi;
      try {
        ffi = require('ffi-napi');
      } catch (error) {
        console.warn('ffi-napi not installed. Run: npm install ffi-napi ref-napi');
        this.nativeLibraryAvailable = false;
        return;
      }
      
      this.hookLibrary = ffi.Library(soPath, {
        'InstallHook': ['bool', []],
        'RemoveHook': ['bool', []],
        'SetWindowHandle': ['bool', ['int']],
        'IsHookActive': ['bool', []]
      });
      
      this.nativeLibraryAvailable = true;
      this.isHooked = false;
    } catch (error) {
      console.error('Failed to load Linux hook library:', error.message);
      this.nativeLibraryAvailable = false;
    }
  }

  /**
   * Install the graphics hook (now just a flag)
   * @returns {boolean} Success status
   */
  installHook() {
    this.isHooked = true;
    return true;
  }

  /**
   * Remove the graphics hook (now just a flag)
   * @returns {boolean} Success status
   */
  removeHook() {
    this.isHooked = false;
    return true;
  }

  /**
   * Check if screen capture is active by looking for known processes
   * @returns {Promise<boolean>} True if capture process is detected
   */
  async isScreenCaptureActive() {
    if (!this.isHooked) {
      return false;
    }

    const processList = await psList();
    return processList.some(p => this.captureProcesses.includes(p.name.toLowerCase()));
  }

  /**
   * Check if the hook is currently active
   * @returns {boolean} Hook status
   */
  isActive() {
    if (!this.hookLibrary || !this.nativeLibraryAvailable) {
      return false;
    }
    
    try {
      return this.hookLibrary.IsHookActive();
    } catch (error) {
      console.error('Failed to check hook status:', error.message);
      return false;
    }
  }
}

module.exports = new GraphicsHook();