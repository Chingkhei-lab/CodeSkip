/**
 * Mobile Companion Mode for Ultracode Clone
 * 
 * This module enables a mobile device to act as an external display
 * for Ultracode, allowing users to view AI responses on their phone
 * during interviews when the main screen is being shared.
 */

const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const qrcode = require('qrcode');
const ip = require('ip');
const path = require('path');
const fs = require('fs');

class MobileCompanion {
  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.wss = new WebSocket.Server({ server: this.server });
    this.port = 8090;
    this.clients = new Set();
    this.messages = [];
    this.maxMessages = 50;
    this.qrCodeDataUrl = '';
    this.initialized = false;
  }

  /**
   * Initialize the mobile companion server
   */
  initialize() {
    if (this.initialized) return;

    // Set up static files
    this.app.use(express.static(path.join(__dirname, 'public')));
    
    // API routes
    this.app.get('/api/connection-info', (req, res) => {
      res.json({
        wsUrl: `ws://${ip.address()}:${this.port}`,
        qrCode: this.qrCodeDataUrl
      });
    });

    // WebSocket connection handling
    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      
      // Send all existing messages to new client
      ws.send(JSON.stringify({
        type: 'init',
        messages: this.messages
      }));
      
      ws.on('message', (message) => {
        try {
          const data = JSON.parse(message);
          
          // Handle client messages
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong' }));
          }
        } catch (e) {
          console.error('Error parsing message:', e);
        }
      });
      
      ws.on('close', () => {
        this.clients.delete(ws);
      });
    });

    // Generate QR code for easy connection
    this._generateQRCode();
    
    // Start the server
    this.server.listen(this.port, () => {
      console.log(`Mobile companion server running on port ${this.port}`);
      console.log(`Connect using: http://${ip.address()}:${this.port}`);
    });
    
    this.initialized = true;
  }

  /**
   * Generate QR code for easy mobile connection
   */
  async _generateQRCode() {
    try {
      const url = `http://${ip.address()}:${this.port}`;
      this.qrCodeDataUrl = await qrcode.toDataURL(url);
      
      // Save QR code as SVG file for display in main app
      const qrSvg = await qrcode.toString(url, { type: 'svg' });
      const qrPath = path.join(__dirname, 'public', 'qrcode.svg');
      fs.writeFileSync(qrPath, qrSvg);
    } catch (e) {
      console.error('Error generating QR code:', e);
    }
  }

  /**
   * Send a message to all connected mobile clients
   * @param {Object} message - Message to send
   */
  sendMessage(message) {
    if (!this.initialized) {
      this.initialize();
    }
    
    // Add timestamp if not present
    if (!message.timestamp) {
      message.timestamp = new Date().toISOString();
    }
    
    // Add to message history
    this.messages.push(message);
    
    // Limit message history size
    if (this.messages.length > this.maxMessages) {
      this.messages = this.messages.slice(-this.maxMessages);
    }
    
    // Broadcast to all clients
    const messageStr = JSON.stringify({
      type: 'message',
      data: message
    });
    
    this.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(messageStr);
      }
    });
  }

  /**
   * Get the QR code for connecting mobile devices
   * @returns {string} QR code data URL
   */
  getQRCode() {
    if (!this.initialized) {
      this.initialize();
    }
    return this.qrCodeDataUrl;
  }

  /**
   * Stop the mobile companion server
   */
  stop() {
    if (!this.initialized) return;
    
    this.server.close();
    this.wss.close();
    this.clients.clear();
    this.initialized = false;
    console.log('Mobile companion server stopped');
  }
}

module.exports = new MobileCompanion();