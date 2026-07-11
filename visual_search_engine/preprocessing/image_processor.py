import cv2
import numpy as np
from PIL import Image

def load_and_preprocess_image(image_path, target_size=(224, 224), remove_bg=True):
    """
    Loads an image, optionally removes the background, and resizes it.
    Returns:
        - processed_np: cv2/numpy image (BGR)
        - pil_image: PIL Image ready for deep learning models (RGB)
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from path: {image_path}")

    if remove_bg:
        img = remove_background(img)

    # Resize
    img_resized = cv2.resize(img, target_size)
    
    # Convert to PIL RGB for transformers / PyTorch
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    
    return img_resized, pil_img

def remove_background(img):
    """
    Removes the background using a GrabCut-based approximation or simple thresholding.
    Jewelry images usually have high contrast with a white/grey background.
    """
    h, w = img.shape[:2]
    if h < 20 or w < 20:
        return img
        
    mask = np.zeros(img.shape[:2], np.uint8)
    
    # Create background and foreground models
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    
    # Define a bounding box excluding the outer 5% border
    rect = (int(w * 0.05), int(h * 0.05), int(w * 0.9), int(h * 0.9))
    
    try:
        # Run GrabCut with 3 iterations
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
        
        # Mask where background is 0 or 2, and foreground is 1 or 3
        mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
        
        # Apply mask to image
        result = img * mask2[:, :, np.newaxis]
        
        # Replace background with white instead of black (standard for jewelry presentation)
        background = np.ones_like(img, dtype=np.uint8) * 255
        inv_mask = cv2.bitwise_not(mask2 * 255)
        bg_part = cv2.bitwise_and(background, background, mask=inv_mask)
        fg_part = cv2.bitwise_and(img, img, mask=mask2*255)
        
        return cv2.add(fg_part, bg_part)
    except Exception as e:
        print(f"Error removing background: {e}. Returning original image.")
        return img
