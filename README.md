# 💎 Aura Jewelry Suite: AI-Powered Visual Search & Recommendation Engine

A Python-based desktop application that integrates **Visual Product Search** (leveraging CLIP, Vision Transformers, and ResNet-50) with a **Hybrid Recommendation Engine** (Matrix Factorization, Neural Collaborative Filtering, and Contextual Bandits) designed specifically for jewelry e-commerce platforms.

---

## 🚀 Key Features

*   **🔍 Visual Search Landing Page**:
    *   Horizontal split-screen layout.
    *   Interactive drag-and-drop or file upload area.
    *   Retrieves the **top 10 most visually similar products** in a clean 3-column grid layout.
    *   **Explainable AI (XAI)** match breakdown profile with Matplotlib comparison graphs plotting RGB color distributions.
*   **🛍️ Personalized Recommendation Engine**:
    *   A shopper playground simulating real-time user clickstream behavior.
    *   **Hybrid Scoring Pipeline**:
        *   **40% Collaborative Filtering** (PyTorch Matrix Factorization & Neural Collaborative Filtering).
        *   **30% Visual Similarity** (Cosine distance in vector space).
        *   **20% Content-affinity & Contextual Bandits** (Adaptive category preferences).
        *   **10% Popularity** (Weighted view/click counts).
*   **⚙️ Admin Dashboard**:
    *   Interactive Matplotlib charts showing interaction metrics.
    *   Complete product table directory.
    *   Index rebuilding and new product insertion with instant vector embedding.
*   **🛡️ Resilient Local Fallback Pipeline**:
    *   If model weights fail to download due to SSL/network limitations, the system automatically uses a hand-crafted **Color Histogram + Coarse Spatial Layout** feature extractor.
    *   Incorporates a **Grayscale Density structural classifier** to differentiate between rings (square-ish & hollow center) and necklaces, ensuring orthogonal vector projection and preventing cross-category matches.

---

## 📂 Project Structure

```text
visual_search_engine/
├── app.py                      # Main entry point (PySide6 application runner)
├── database/
│   ├── connection.py           # SQLite connection manager
│   └── schema.py               # Table structures (Products, Users, Events)
├── preprocessing/
│   └── image_processor.py      # GrabCut background subtraction & normalization
├── models/
│   ├── embedder.py             # CLIP/ViT/ResNet50 + Fallback feature generator
│   └── recommender.py          # CF, NCF (Neural Recommender) & Contextual Bandits
├── retrieval/
│   └── search_index.py         # FAISS Vector Search registry with score calibration
├── services/
│   └── tracking.py             # User clickstream, dwell time & event logger
├── gui/
│   ├── main_window.py          # PySide6 main tab container layout
│   ├── visual_search_tab.py    # XAI visual search landing page view
│   ├── customer_view.py        # Customer shopping & recommendation portal
│   ├── admin_view.py           # Matplotlib dashboard & inventory tables
│   └── components.py           # Dark theme styles & customizable widget cards
└── utils/
    └── data_generator.py       # Tanishq dataset importer & synthetic data seeder
```

---

## 🛠️ Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/mayank-dashore/visual-search-product.git
cd visual-search-product
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
```

### 3. Activate the Environment & Install Dependencies
On Windows:
```powershell
.\venv\Scripts\activate
pip install PySide6 torch torchvision transformers faiss-cpu numpy pandas opencv-python scikit-learn matplotlib
```

---

## 💎 Loading the Tanishq Jewellery Dataset

To load your Tanishq Jewellery images:
1. Extract your dataset.
2. Put the category folders (`Rings`, `Necklaces`, etc.) inside:
   `visual_search_engine/datasets/tanishq-jewellery-dataset/`
3. Seed the database and generate visual vectors:
   ```powershell
   $env:PYTHONPATH="visual_search_engine"; .\venv\Scripts\python visual_search_engine/utils/data_generator.py
   ```

---

## 🚀 Running the Application

Launch the Aura Jewelry Suite using:

```powershell
$env:PYTHONPATH="visual_search_engine"; .\venv\Scripts\python visual_search_engine/app.py
```
