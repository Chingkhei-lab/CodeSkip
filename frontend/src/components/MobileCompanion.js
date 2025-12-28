import React, { useState, useEffect } from 'react';
const { ipcRenderer } = window.require('electron');

const MobileCompanion = () => {
  const [qrCode, setQrCode] = useState('');
  const [showQR, setShowQR] = useState(false);

  useEffect(() => {
    const fetchQRCode = async () => {
      try {
        const result = await ipcRenderer.invoke('get-mobile-qr');
        if (result.qrCode) {
          setQrCode(result.qrCode);
        }
      } catch (error) {
        console.error('Failed to get QR code:', error);
      }
    };

    fetchQRCode();
  }, []);

  return (
    <div className="mobile-companion">
      <button 
        className="mobile-toggle"
        onClick={() => setShowQR(!showQR)}
      >
        {showQR ? 'Hide Mobile QR' : 'Show Mobile QR'}
      </button>
      
      {showQR && qrCode && (
        <div className="qr-container">
          <h3>Mobile Companion Mode</h3>
          <p>Scan this QR code with your mobile device to view AI responses on your phone</p>
          <div className="qr-code" dangerouslySetInnerHTML={{ __html: qrCode }} />
        </div>
      )}
    </div>
  );
};

export default MobileCompanion;