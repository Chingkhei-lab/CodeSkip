import cv2
import numpy as np
import pytesseract
from PIL import ImageGrab
import os
import logging
import tempfile
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class ScreenCapture:
    def __init__(self):
        """Initialize screen capture with secure settings"""
        # Configure Tesseract path from env or default install
        try:
            tess_cmd = os.getenv('TESSERACT_PATH')
            if tess_cmd and os.path.exists(tess_cmd):
                pytesseract.pytesseract.tesseract_cmd = tess_cmd
                logger.info(f"✓ Tesseract configured: {tess_cmd}")
            else:
                default = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                if os.path.exists(default):
                    pytesseract.pytesseract.tesseract_cmd = default
                    logger.info(f"✓ Tesseract found at default location")
                else:
                    logger.warning("⚠ Tesseract not found, OCR may fail")
        except Exception as e:
            logger.error(f"Failed to configure Tesseract: {e}")
        
        self.last_capture = None
        self.region = None  # (x1, y1, x2, y2) for custom region
        self._temp_files = []  # Track temp files for cleanup
    
    def set_capture_region(self, x1: int, y1: int, x2: int, y2: int):
        """
        Set custom region for screen capture
        
        Args:
            x1, y1: Top-left coordinates
            x2, y2: Bottom-right coordinates
        """
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Invalid region: x2 must be > x1 and y2 must be > y1")
        self.region = (x1, y1, x2, y2)
        logger.info(f"Capture region set: ({x1}, {y1}) to ({x2}, {y2})")
    
    def capture_screen(self) -> np.ndarray:
        """
        Capture screen or defined region
        
        Returns:
            numpy.ndarray: Captured image
        """
        try:
            if self.region:
                screenshot = ImageGrab.grab(bbox=self.region)
                logger.debug(f"Captured region: {self.region}")
            else:
                screenshot = ImageGrab.grab()
                logger.debug("Captured full screen")
            
            self.last_capture = np.array(screenshot)
            return self.last_capture
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            raise
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results
        
        Args:
            image: Input image
            
        Returns:
            numpy.ndarray: Preprocessed image
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Apply threshold to get black and white image
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
            
            # Noise removal
            kernel = np.ones((1, 1), np.uint8)
            opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            
            return opening
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image  # Return original if preprocessing fails
    
    def extract_text(self, image: np.ndarray) -> str:
        """
        Extract text from image using OCR
        
        Args:
            image: Input image
            
        Returns:
            str: Extracted text
        """
        try:
            # For code, we use a configuration optimized for structured text
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            logger.info(f"OCR extracted {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"OCR text extraction failed: {e}")
            return ""
    
    def capture_and_extract_text(self) -> str:
        """
        Capture screen and extract text in one step
        
        Returns:
            str: Extracted text from screen
        """
        try:
            image = self.capture_screen()
            processed_image = self.preprocess_image(image)
            text = self.extract_text(processed_image)
            
            # Security: Don't log sensitive screen content
            logger.info(f"Screen capture and OCR complete: {len(text)} chars extracted")
            return text
        except Exception as e:
            logger.error(f"Capture and extract failed: {e}")
            return ""
    
    def save_debug_image(self, path: Optional[str] = None) -> bool:
        """
        Save last captured image for debugging
        
        Args:
            path: Output file path. If None, uses temp file.
            
        Returns:
            bool: True if saved successfully
        """
        if self.last_capture is None:
            logger.warning("No capture available to save")
            return False
        
        try:
            if path is None:
                # Create secure temp file
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix='.png',
                    prefix='debug_capture_'
                )
                path = temp_file.name
                temp_file.close()
                self._temp_files.append(path)
                logger.info(f"Saving debug image to temp file: {path}")
            
            cv2.imwrite(path, self.last_capture)
            logger.info(f"✓ Debug image saved: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")
            return False
    
    def secure_delete(self, filepath: str):
        """
        Securely delete file by overwriting with random data first
        
        Args:
            filepath: Path to file to delete
        """
        try:
            if not os.path.exists(filepath):
                return
            
            # Overwrite with random data
            file_size = os.path.getsize(filepath)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(file_size))
            
            # Delete the file
            os.unlink(filepath)
            logger.debug(f"Securely deleted: {filepath}")
        except Exception as e:
            logger.error(f"Secure deletion failed for {filepath}: {e}")
            try:
                # Fallback to normal delete
                os.unlink(filepath)
            except:
                pass
    
    def cleanup(self):
        """Clean up temporary files securely"""
        for temp_file in self._temp_files:
            self.secure_delete(temp_file)
        self._temp_files.clear()
        logger.info("✓ Cleanup complete")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        try:
            self.cleanup()
        except:
            pass
