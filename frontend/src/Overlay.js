import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Box, IconButton, TextField, Button } from '@mui/material';
import { Close, Minimize, Settings, Send } from '@mui/icons-material';

const Overlay = () => {
  const [isVisible, setIsVisible] = useState(true);
  const [isStealthMode, setIsStealthMode] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isElectron, setIsElectron] = useState(false);

  useEffect(() => {
    // Check if running in Electron
    const userAgent = navigator.userAgent.toLowerCase();
    const isElectronEnv = userAgent.includes(' electron/');
    setIsElectron(isElectronEnv);

    if (isElectronEnv) {
      // Only try to use Electron APIs if running in Electron
      const electron = window.require ? window.require('electron') : null;
      const ipcRenderer = electron ? electron.ipcRenderer : null;

      if (ipcRenderer) {
        // Listen for toggle events from main process
        ipcRenderer.on('toggle-main-window', (event, visible) => {
          setIsVisible(visible);
        });

        ipcRenderer.on('stealth-mode-changed', (event, isStealth) => {
          setIsStealthMode(isStealth);
        });

        // Request initial state
        ipcRenderer.send('request-initial-state');
      }
    }
  }, []);

  const handleClose = () => {
    setIsVisible(false);
    if (isElectron && window.require) {
      const electron = window.require('electron');
      electron.ipcRenderer.send('toggle-main-window', false);
    }
  };

  const handleMinimize = () => {
    setIsVisible(false);
    if (isElectron && window.require) {
      const electron = window.require('electron');
      electron.ipcRenderer.send('toggle-main-window', false);
    }
  };

  const handleSendMessage = () => {
    if (inputText.trim()) {
      const newMessage = {
        id: Date.now(),
        text: inputText,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages([...messages, newMessage]);
      setInputText('');

      // Send message to main process
      if (isElectron && window.require) {
        const electron = window.require('electron');
        electron.ipcRenderer.send('ai-response', { content: inputText });
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!isVisible) {
    return null;
  }

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 20,
        right: 20,
        width: 400,
        height: 150,
        zIndex: 9999,
        pointerEvents: isStealthMode ? 'none' : 'auto',
      }}
    >
      <Card
        sx={{
          height: '100%',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(10px)',
          borderRadius: 2,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
        }}
      >
        <CardContent sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold', color: '#1976d2' }}>
              UltraCode
            </Typography>
            <Box>
              <IconButton size="small" sx={{ color: '#666' }}>
                <Settings fontSize="small" />
              </IconButton>
              <IconButton size="small" sx={{ color: '#666' }} onClick={handleMinimize}>
                <Minimize fontSize="small" />
              </IconButton>
              <IconButton size="small" sx={{ color: '#666' }} onClick={handleClose}>
                <Close fontSize="small" />
              </IconButton>
            </Box>
          </Box>

          {/* Content */}
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Typography variant="body2" sx={{ color: '#666', textAlign: 'center', mb: 2 }}>
              {isElectron ? 'AI Coding Assistant Ready' : 'Running in Browser Mode'}
            </Typography>
            
            {/* Simple input for quick commands */}
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                size="small"
                placeholder="Ask anything..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                sx={{
                  flex: 1,
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                  }
                }}
              />
              <Button
                variant="contained"
                size="small"
                onClick={handleSendMessage}
                sx={{ 
                  borderRadius: 2,
                  backgroundColor: '#1976d2',
                  '&:hover': { backgroundColor: '#1565c0' }
                }}
              >
                <Send fontSize="small" />
              </Button>
            </Box>
          </Box>

          {/* Status indicator */}
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 1 }}>
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: isStealthMode ? '#ff9800' : '#4caf50',
                animation: 'pulse 2s infinite',
              }}
            />
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default Overlay;