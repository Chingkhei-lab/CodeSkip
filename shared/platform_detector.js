/**
 * Platform Detector Module f
 */

const { BrowserWindow } = require('electron');

class PlatformDetector {
  constructor() {
    this.platforms = {
      'codesignal.com': {
        name: 'CodeSignal',
        selectors: ['.task-description', '.cm-editor'],
        adaptations: {
          hideOnScreenShare: true,
          useAlternativeRendering: true,
          captureRegions: ['#code-editor', '.problem-statement']
        }
      },
      'hackerrank.com': {
        name: 'HackerRank',
        selectors: ['.challenge-body', '.monaco-editor'],
        adaptations: {
          hideOnScreenShare: true,
          useAlternativeRendering: true,
          captureRegions: ['.monaco-editor-background', '.problem-statement']
        }
      },
      'coderpad.io': {
        name: 'CoderPad',
        selectors: ['.CodeMirror', '.question-description'],
        adaptations: {
          hideOnScreenShare: true,
          useAlternativeRendering: true,
          captureRegions: ['.CodeMirror', '.question-description']
        }
      },
      'leetcode.com': {
        name: 'LeetCode',
        selectors: ['.content__1Y2H', '.monaco-editor'],
        adaptations: {
          hideOnScreenShare: true,
          useAlternativeRendering: true,
          captureRegions: ['.monaco-editor-background', '.content__1Y2H']
        }
      },
      'interviewbit.com': {
        name: 'InterviewBit',
        selectors: ['.problem-statement', '.ace_editor'],
        adaptations: {
          hideOnScreenShare: true,
          useAlternativeRendering: true,
          captureRegions: ['.ace_editor', '.problem-statement']
        }
      }
    };
    
    this.currentPlatform = null;
    this.detectionInterval = null;
    this.onPlatformDetected = null;
  }

  /**
   * Start continuous platform detection
   * @param {BrowserWindow} mainWindow - The main Electron window
   * @param {Function} callback - Called when platform is detected or changed
   */
  startDetection(mainWindow, callback) {
    if (!mainWindow) {
      console.error('No main window provided for platform detection');
      return;
    }

    this.onPlatformDetected = callback;
    
    // Clear any existing detection interval
    if (this.detectionInterval) {
      clearInterval(this.detectionInterval);
    }
    
    // Run detection every 5 seconds
    this.detectionInterval = setInterval(() => {
      this.detectPlatform(mainWindow);
    }, 5000);
    
    // Run initial detection
    this.detectPlatform(mainWindow);
  }

  /**
   * Stop platform detection
   */
  stopDetection() {
    if (this.detectionInterval) {
      clearInterval(this.detectionInterval);
      this.detectionInterval = null;
    }
  }

  /**
   * Detect the current platform
   * @param {BrowserWindow} mainWindow - The main Electron window
   */
  async detectPlatform(mainWindow) {
    try {
      // Get current URL
      const url = await mainWindow.webContents.getURL();
      if (!url || url === 'about:blank') return;
      
      // Extract domain from URL
      const domain = new URL(url).hostname;
      
      // Check if we're on a known platform
      let detectedPlatform = null;
      for (const [platformDomain, platformInfo] of Object.entries(this.platforms)) {
        if (domain.includes(platformDomain)) {
          detectedPlatform = {
            domain: platformDomain,
            ...platformInfo
          };
          break;
        }
      }
      
      // If platform changed, verify with DOM elements
      if (detectedPlatform && detectedPlatform.domain !== (this.currentPlatform?.domain || null)) {
        const confirmed = await this.confirmPlatformWithDOM(mainWindow, detectedPlatform);
        if (confirmed) {
          console.log(`Detected platform: ${detectedPlatform.name}`);
          this.currentPlatform = detectedPlatform;
          
          // Notify callback if provided
          if (this.onPlatformDetected) {
            this.onPlatformDetected(detectedPlatform);
          }
        }
      }
      
      // If we're not on a known platform anymore, reset
      if (!detectedPlatform && this.currentPlatform) {
        console.log('Left known platform');
        this.currentPlatform = null;
        
        // Notify callback if provided
        if (this.onPlatformDetected) {
          this.onPlatformDetected(null);
        }
      }
    } catch (error) {
      console.error('Error detecting platform:', error);
    }
  }

  /**
   * Confirm platform detection by checking for specific DOM elements
   * @param {BrowserWindow} mainWindow - The main Electron window
   * @param {Object} platform - Platform information
   * @returns {Promise<boolean>} Whether the platform is confirmed
   */
  async confirmPlatformWithDOM(mainWindow, platform) {
    if (!platform.selectors || platform.selectors.length === 0) {
      return true; // No selectors to check
    }
    
    try {
      // Check if at least one selector exists in the DOM
      const results = await mainWindow.webContents.executeJavaScript(`
        (function() {
          const selectors = ${JSON.stringify(platform.selectors)};
          for (const selector of selectors) {
            if (document.querySelector(selector)) {
              return true;
            }
          }
          return false;
        })()
      `);
      
      return results;
    } catch (error) {
      console.error('Error confirming platform with DOM:', error);
      return false;
    }
  }

  /**
   * Get the current detected platform
   * @returns {Object|null} Current platform information or null
   */
  getCurrentPlatform() {
    return this.currentPlatform;
  }

  /**
   * Get adaptations for the current platform
   * @returns {Object|null} Adaptation settings or null
   */
  getAdaptations() {
    return this.currentPlatform?.adaptations || null;
  }

  /**
   * Check if we're currently on a specific platform
   * @param {string} platformName - Name of the platform to check
   * @returns {boolean} Whether we're on the specified platform
   */
  isPlatform(platformName) {
    return this.currentPlatform?.name === platformName;
  }

  /**
   * Get optimal capture regions for the current platform
   * @returns {Array<string>} Array of CSS selectors for capture regions
   */
  getCaptureRegions() {
    return this.currentPlatform?.adaptations?.captureRegions || [];
  }
}

module.exports = new PlatformDetector();