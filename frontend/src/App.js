import React, { useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import KeyboardIcon from '@mui/icons-material/Keyboard';
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import MicIcon from '@mui/icons-material/Mic';
import ScreenshotMonitorIcon from '@mui/icons-material/ScreenshotMonitor';

// Electron integration
const isElectron = !!(window && window.process && window.process.type);
const ipcRenderer = isElectron ? window.require('electron').ipcRenderer : null;

// Create theme
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
  },
});

function App() {
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [stealthMode, setStealthMode] = useState(false);
  const [backendStatus, setBackendStatus] = useState('Disconnected');
  const [audioStatus, setAudioStatus] = useState('Inactive');
  const [screenStatus, setScreenStatus] = useState('Inactive');

  useEffect(() => {
    // Listen for stealth mode changes from main process
    if (!ipcRenderer) return;
    ipcRenderer.on('stealth-mode-changed', (event, isStealthMode) => {
      setStealthMode(isStealthMode);
    });
    checkBackendStatus();
    return () => {
      ipcRenderer?.removeAllListeners('stealth-mode-changed');
    };
  }, []);

  const toggleOverlay = () => {
    const newVisibility = !overlayVisible;
    setOverlayVisible(newVisibility);
    ipcRenderer.send('set-overlay-visibility', newVisibility);
  };

  const checkBackendStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/status');
      if (response.ok) {
        const data = await response.json();
        setBackendStatus(data.status === 'ok' ? 'Connected' : 'Error');
        setAudioStatus(data.audio_status || 'Inactive');
        setScreenStatus(data.screen_status || 'Inactive');
      } else {
        setBackendStatus('Disconnected');
      }
    } catch (error) {
      setBackendStatus('Disconnected');
    }
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
        <Paper elevation={3} sx={{ p: 3 }}>
          <Typography variant="h4" gutterBottom align="center">
            Ultracode Control Panel
          </Typography>
          <Divider sx={{ mb: 3 }} />

          <Grid container spacing={3} alignItems="center">
            <Grid item xs={12} md={6}>
              <Typography variant="h6">Global Settings</Typography>
              <FormControlLabel
                control={<Switch checked={overlayVisible} onChange={toggleOverlay} />}
                label="Show Overlay"
              />
              <FormControlLabel
                control={<Switch checked={stealthMode} disabled />}
                label="Stealth Mode"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="h6">Backend Status</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="body1" sx={{ minWidth: 120 }}>
                  Connection:
                </Typography>
                <Typography variant="body1" color={backendStatus === 'Connected' ? 'success.main' : 'error.main'}>
                  {backendStatus}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <MicIcon sx={{ mr: 1 }} />
                <Typography variant="body1" sx={{ minWidth: 100 }}>
                  Audio:
                </Typography>
                <Typography variant="body1" color={audioStatus === 'active' ? 'success.main' : 'text.secondary'}>
                  {audioStatus}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <ScreenshotMonitorIcon sx={{ mr: 1 }} />
                <Typography variant="body1" sx={{ minWidth: 100 }}>
                  Screen:
                </Typography>
                <Typography variant="body1" color={screenStatus === 'active' ? 'success.main' : 'text.secondary'}>
                  {screenStatus}
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 3 }} />

          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
            <Button variant="contained" startIcon={<KeyboardIcon />}>
              Configure Shortcuts
            </Button>
            <Button variant="outlined" onClick={checkBackendStatus}>
              Refresh Status
            </Button>
          </Box>
        </Paper>
      </Container>
    </ThemeProvider>
  );
}

export default App;