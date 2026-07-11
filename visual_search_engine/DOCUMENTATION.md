# Aura Jewelry Suite: Developer Documentation

This document explains the architecture, visual search heuristics, recommendation logic, database models, and GUI layout of the **Aura Jewelry Suite** desktop application.

---

## 📂 Project Directory Structure

The application is structured into modular components:

```text
visual_search_engine/
├── app.py                      # Main application entry point (PySide6 runner)
├── database/
│   ├── connection.py           # SQLite connection establishment
│   └── schema.py               # Database table structure initialization
├── preprocessing/
│   └── image_processor.py      # GrabCut background subtraction & normalization
├── retrieval/
│   └── search_index.py         # FAISS Vector search index & calibration wrapper
├── models/
│   ├── embedder.py             # Feature extractor (CLIP/ViT/ResNet50 + Fallback CV)
│   └── recommender.py          # Hybrid Recommender (CF, NCF, Contextual Bandits)
├── services/
│   └── tracking.py             # User interaction logger (views, clicks, purchases)
├── gui/
│   ├── main_window.py          # Tab container window
│   ├── visual_search_tab.py    # XAI visual search landing page view
│   ├── customer_view.py        # Personalized recommendation portal
│   ├── admin_view.py           # Metrics graphs & product table dashboard
│   └── components.py           # Custom modern cards, stylesheets & drag-drop loaders
└── utils/
    └── data_generator.py       # Tanishq importer & synthetic data seeder
```

---

## 🎨 1. GUI Architecture & UX Design

The desktop application is built with **PySide6** and styled using a customized, responsive Slate-Dark theme stylesheet (designed with CSS parameters for rounded borders, active gradients, and micro-hovers).

### Tab Registry:
1. **🔍 Visual Search Landing Page** (in [visual_search_tab.py](file:///c:/Users/Mayank/Spark-Practice-Mayank/personal/visual-search-product/visual_search_engine/gui/visual_search_tab.py)):
   - A split-screen dashboard layout.
   - The **Left Panel (Width 320px)** houses the Drag & Drop area, Large Search Previews, and clear controls (`🧹 Clear` & `🔄 Re-Search`).
   - The **Right Panel** features a spacious 3-column matching grid displaying the top 10 matches.
   - Clicking **`🔍 Explain Match`** launches a popup comparisons dialog showing side-by-side images, score breakdowns, and an RGB overlap graph.
2. **🛍️ Recommender Sandbox** (in [customer_view.py](file:///c:/Users/Mayank/Spark-Practice-Mayank/personal/visual-search-product/visual_search_engine/gui/customer_view.py)):
   - Implements customer context browsing. You can switch customer profiles (e.g. `user_1` to `user_2`), perform simulated events (Click `👁️`, Wishlist `❤️`, Buy `🛒`), and watch their personalized recommendations recalculate instantly.
3. **⚙️ Admin Dashboard** (in [admin_view.py](file:///c:/Users/Mayank/Spark-Practice-Mayank/personal/visual-search-product/visual_search_engine/gui/admin_view.py)):
   - Displays real-time database logs, user interaction volume charts (rendered via Matplotlib), and forms to add products and rebuild indexes.

---

## 📷 2. Hand-Crafted Fallback Computer Vision Pipeline

Due to potential local SSL validation barriers (`[SSL: CERTIFICATE_VERIFY_FAILED]`), the embedder ([embedder.py](file:///c:/Users/Mayank/Spark-Practice-Mayank/personal/visual-search-product/visual_search_engine/models/embedder.py)) implements a dual-mode feature extractor:

### Mode A: Deep Learning (CLIP, ViT, ResNet-50)
If internet access is clear and certificates validate, the system downloads weights, extracts deep features, normalizes them, and concatenates them into a `3328-dimension` vector.

### Mode B: Hand-Crafted Visual Feature Fallback
If the model weights fail to download, the system generates visual embeddings locally using:
1. **Color Histograms (1100-dim)**: Split R, G, B channels of a resized $64\times 64$ image and bin their pixel values into 64 intervals. Projected deterministically to `1100` dimensions to capture color distributions (e.g. gold vs platinum vs ruby).
2. **Coarse Spatial Layout (1100-dim)**: Convert the image to grayscale and flatten it. Projected to `1100` dimensions to capture spatial density.
3. **Grayscale Density Shape Classifier**:
   - Resizes the image to $32\times 32$ and thresholds pixels (< 240) to locate the jewelry foreground.
   - Computes the aspect ratio of the bounding box.
   - Analyzes center hollowness (average pixel density in the central $10\times 10$ pixels).
   - Classifies the shape structure: **Circular & Hollow = Rings**; **Wider or Solid Center = Necklaces**.
4. **Category Orthogonal Shifts**: 
   - A ring embedding is shifted into a positive region in the first half of the vector space and negative in the second half.
   - A necklace embedding is shifted in the opposite direction.
   - *Why this works*: It forces rings and necklaces to be completely orthogonal in vector space, preventing cross-category mismatching.

---

## 📊 3. Similarity Score Calibration & XAI Explainability

### Calibration Logic
Cosine similarity dot products from FAISS or NumPy similarity matrix search are mapped to user-facing percentages:
- Perfect match: **100% Match**
- Similar items: Calibrated to map raw similarities to **75% – 98%** to align with real-world computer vision accuracy presentation.
$$\text{calibrated\_score} = 0.75 + (0.23 \times \text{raw\_score})$$

### Explainability Dialogue (XAI)
When clicking **Explain Match**, the dialog computes the RGB intensity profiles of the Query and Match images. Matplotlib charts plot these distributions side-by-side, visually showing the user how closely the color channels align (e.g., matching the golden spectrum curve).

---

## 📈 4. Recommender Engine Mechanics

The hybrid recommender ([recommender.py](file:///c:/Users/Mayank/Spark-Practice-Mayank/personal/visual-search-product/visual_search_engine/models/recommender.py)) utilizes PyTorch to train recommendation weights on interaction history logs:

1. **Matrix Factorization (CF) (40% Weight)**: Maps user and item indexes to a shared latent embedding space ($D=32$), estimating preferences based on vector dot products plus user/item biases.
2. **Neural Collaborative Filtering (NCF)**: Connects concatenated user and item embeddings through a Multi-Layer Perceptron (MLP) with a Sigmoid output to score interaction likelihood.
3. **Visual Similarity (30% Weight)**: Incorporates current visual context from the vector index search to boost similar-looking catalog items.
4. **Content-Based & Contextual Bandits (20% Weight)**: Leverages the user's historical category affinity. Includes an exploration factor (Multi-Armed Bandit logic) to suggest novel products.
5. **Popularity (10% Weight)**: Baseline rating score computed by weighting actions (Views = 1, Clicks = 2, Wishlist = 3, Purchases = 5).

---

## 🚀 Execution Instructions

First, activate the virtual environment and run the application:

```powershell
# Set path and run the application
$env:PYTHONPATH="visual_search_engine"; .\venv\Scripts\python visual_search_engine/app.py
```
