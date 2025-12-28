/**
 * Error Handler Module for Ultracode Clone
 * 
 * This module provides robust error handling and recovery mechanisms
 * for the application, ensuring graceful degradation and resilience.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

class ErrorHandler {
  constructor() {
    // Use temp directory initially, will update when app is ready
    this.logDir = path.join(os.tmpdir(), 'ultracode-logs');
    this.errorLog = path.join(this.logDir, 'error.log');
    this.maxLogSize = 10 * 1024 * 1024; // 10MB
    this.errorListeners = [];
    this.recoveryStrategies = {};
    this.isAppReady = false;
    
    // Create log directory if it doesn't exist
    this._ensureLogDirectory();
    
    // Set up global error handlers
    this._setupGlobalHandlers();
  }

  /**
   * Initialize with Electron app instance (call this when app is ready)
   * @param {Electron.App} app - Electron app instance
   */
  initializeWithApp(app) {
    if (app && app.getPath) {
      try {
        this.logDir = path.join(app.getPath('userData'), 'logs');
        this.errorLog = path.join(this.logDir, 'error.log');
        this._ensureLogDirectory();
        this.isAppReady = true;
        console.log('Error handler initialized with app paths');
      } catch (error) {
        console.error('Failed to initialize error handler with app:', error);
      }
    }
  }

  /**
   * Ensure log directory exists
   */
  _ensureLogDirectory() {
    try {
      if (!fs.existsSync(this.logDir)) {
        fs.mkdirSync(this.logDir, { recursive: true });
      }
    } catch (error) {
      console.error('Failed to create log directory:', error);
    }
  }

  /**
   * Set up global error handlers
   */
  _setupGlobalHandlers() {
    // Handle uncaught exceptions
    process.on('uncaughtException', (error) => {
      console.error('Uncaught Exception:', error);
      this.handleError('uncaughtException', error);
    });
    
    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason) => {
      console.error('Unhandled Rejection:', reason);
      this.handleError('unhandledRejection', reason);
    });
  }

  /**
   * Log an error to file
   * @param {string} type - Error type
   * @param {Error|string} error - Error object or message
   */
  logError(type, error) {
    try {
      // Rotate log if it's too large
      this._rotateLogIfNeeded();
      
      const timestamp = new Date().toISOString();
      const errorMessage = error instanceof Error ? error.stack || error.message : error.toString();
      const logEntry = `[${timestamp}] [${type}] ${errorMessage}\n`;
      
      fs.appendFileSync(this.errorLog, logEntry);
    } catch (e) {
      console.error('Failed to log error:', e);
    }
  }

  /**
   * Rotate log file if it exceeds the maximum size
   */
  _rotateLogIfNeeded() {
    try {
      if (fs.existsSync(this.errorLog)) {
        const stats = fs.statSync(this.errorLog);
        if (stats.size > this.maxLogSize) {
          const backupLog = `${this.errorLog}.${Date.now()}.bak`;
          fs.renameSync(this.errorLog, backupLog);
        }
      }
    } catch (e) {
      console.error('Failed to rotate log:', e);
    }
  }

  /**
   * Handle an error with appropriate recovery strategy
   * @param {string} type - Error type
   * @param {Error|string} error - Error object or message
   */
  handleError(type, error) {
    // Log the error
    this.logError(type, error);
    
    // Console output for debugging
    console.error(`[${type}]`, error);
    
    // Notify all error listeners
    this._notifyListeners(type, error);
    
    // Apply recovery strategy if available
    this._applyRecoveryStrategy(type, error);
  }

  /**
   * Notify all error listeners
   * @param {string} type - Error type
   * @param {Error|string} error - Error object or message
   */
  _notifyListeners(type, error) {
    for (const listener of this.errorListeners) {
      try {
        listener(type, error);
      } catch (e) {
        console.error('Error in error listener:', e);
      }
    }
  }

  /**
   * Apply recovery strategy for the error
   * @param {string} type - Error type
   * @param {Error|string} error - Error object or message
   */
  _applyRecoveryStrategy(type, error) {
    // Get error code or use type as fallback
    const errorCode = error.code || type;
    
    // Find matching recovery strategy
    const strategy = this.recoveryStrategies[errorCode] || this.recoveryStrategies[type];
    
    if (strategy) {
      try {
        strategy(error);
      } catch (e) {
        console.error('Error in recovery strategy:', e);
      }
    }
  }

  /**
   * Add an error listener
   * @param {Function} listener - Function to call when an error occurs
   */
  addListener(listener) {
    if (typeof listener === 'function' && !this.errorListeners.includes(listener)) {
      this.errorListeners.push(listener);
    }
  }

  /**
   * Remove an error listener
   * @param {Function} listener - Listener to remove
   */
  removeListener(listener) {
    const index = this.errorListeners.indexOf(listener);
    if (index !== -1) {
      this.errorListeners.splice(index, 1);
    }
  }

  /**
   * Register a recovery strategy for a specific error code
   * @param {string} errorCode - Error code or type
   * @param {Function} strategy - Recovery function
   */
  registerRecoveryStrategy(errorCode, strategy) {
    if (typeof strategy === 'function') {
      this.recoveryStrategies[errorCode] = strategy;
    }
  }

  /**
   * Get all logged errors
   * @param {number} maxLines - Maximum number of lines to return
   * @returns {string} Error log content
   */
  getErrorLog(maxLines = 100) {
    try {
      if (fs.existsSync(this.errorLog)) {
        const content = fs.readFileSync(this.errorLog, 'utf8');
        if (maxLines) {
          const lines = content.split('\n');
          return lines.slice(-maxLines).join('\n');
        }
        return content;
      }
    } catch (e) {
      console.error('Failed to read error log:', e);
    }
    return '';
  }

  /**
   * Clear the error log
   */
  clearErrorLog() {
    try {
      if (fs.existsSync(this.errorLog)) {
        fs.writeFileSync(this.errorLog, '');
      }
    } catch (e) {
      console.error('Failed to clear error log:', e);
    }
  }
}

module.exports = new ErrorHandler();