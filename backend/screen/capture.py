import cv2
import numpy as np
import pytesseract
from PIL import ImageGrab
import os

class ScreenCapture:
    def __init__(self):
        # Configure Tesseract path from env or default install, if not in PATH
        try:
            tess_cmd = os.getenv('TESSERACT_PATH')
            if tess_cmd and os.path.exists(tess_cmd):
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
            else:
                default = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                if os.path.exists(default):
                    pytesseract.pytesseract.tesseract_cmd = default
        except Exception:
            # Fail silently; pytesseract will attempt to use PATH
            pass
        self.last_capture = None
        self.region = None  # (x1, y1, x2, y2) for custom region
    
    def set_capture_region(self, x1, y1, x2, y2):
        """Set custom region for screen capture"""
        self.region = (x1, y1, x2, y2)
    
    def capture_screen(self):
        """Capture screen or defined region"""
        if self.region:
            screenshot = ImageGrab.grab(bbox=self.region)
        else:
            screenshot = ImageGrab.grab()
        
        self.last_capture = np.array(screenshot)
        return self.last_capture
    
    def preprocess_image(self, image):
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get black and white image
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        
        # Noise removal
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return opening
    
    def extract_text(self, image):
        """Extract text from image using OCR"""
        # For code, we use a configuration optimized for structured text
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(image, config=custom_config)
        return text
    
    def capture_and_extract_text(self):
        """Capture screen and extract text in one step"""
        image = self.capture_screen()
        processed_image = self.preprocess_image(image)
        text = self.extract_text(processed_image)
        return text
    
    def save_debug_image(self, path="debug_capture.png"):
        """Save last captured image for debugging"""
        if self.last_capture is not None:
            cv2.imwrite(path, self.last_capture)
            return True
        return False