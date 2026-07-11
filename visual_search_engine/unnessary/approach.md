# AI-Powered Visual Search & Recommendation Engine: Approach & Architecture

This document explains the architectural approach, technical decisions, and visual search optimization strategies implemented in the **Aura Jewelry Suite**.

---

## 🛠️ How to Run the Application

You can launch the desktop application by running this command in your PowerShell terminal:

```powershell
$env:PYTHONPATH="visual_search_engine"; .\venv\Scripts\python visual_search_engine/app.py
```

---

## 🔍 Why Did a Ring Match a Necklace at 95%?

There are two primary reasons why this "cross-category match" occurred with a high score:

1. **Fallback Feature Extraction**: 
   Because of local SSL certificate verification failures (`[SSL: CERTIFICATE_VERIFY_FAILED]`), PyTorch could not download pre-trained deep learning weights for CLIP, ViT, or ResNet-50. The application automatically switched to its robust hand-crafted fallback vector extractor.
   This fallback uses:
   - **Color Histograms** (distribution of gold/silver/gem pixels).
   - **Coarse Grayscale Layout** (brightness in grid sections).
   
   Since both rings and necklaces in the Tanishq dataset are photographed on clean white backgrounds and consist of metallic/gold colors, their color profiles are nearly identical. Furthermore, downsampled grids of circular rings and curved necklaces can have overlapping layout densities, leading to similar raw cosine dot products.

2. **Similarity Calibration**:
   To present clean, customer-facing scores, raw cosine similarities are mapped to a range of `75%` to `98%` using:
   $$\text{calibrated\_score} = 0.75 + (0.23 \times \text{raw\_score})$$
   A moderate raw similarity score of `0.85` gets calibrated to `95%` similarity.

---

## 💡 How We Fix It (Visual Optimization Approach)

To improve accuracy and prevent cross-category mismatching without relying on internet-dependent neural networks, we implement a **Grayscale Density Classifier** in the feature generator:

### 1. Aspect Ratio and Center-Hollowness Check
- **Rings** are highly square-shaped (aspect ratio $\approx 1.0$) and **hollow in the center** (high white-pixel density in the center block, surrounded by a ring of dark/jewelry pixels).
- **Necklaces** have high density in the bottom/center where the pendant hangs and are typically wider.

### 2. Category-Bias Embedding Injection
We calculate these structural metrics for both query images and database products. We inject a categorical representation into the vector space. During the search, products matching the detected query structure receive a matching reward, while mismatched structures (e.g. comparing a hollow circle to a hanging necklace curve) are penalized, pushing the incorrect categories down the match hierarchy.
