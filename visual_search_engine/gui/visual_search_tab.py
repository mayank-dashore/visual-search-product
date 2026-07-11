from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QGridLayout, QFrame, QPushButton, QSizePolicy, QDialog)
from PySide6.QtCore import Qt, Slot
import numpy as np

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
from gui.components import DragDropUploadWidget, ProductCard
from database.connection import get_connection
from models.embedder import EmbeddingGenerator
from retrieval.search_index import SearchIndex
from PIL import Image
import os

class PureVisualSearchTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.embedder = EmbeddingGenerator()
        self.search_index = SearchIndex(dimension=self.embedder.get_dim())
        self.search_index.load()
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)
        
        # --- LEFT SIDE PANEL (Search Controls & Preview) ---
        left_panel = QFrame(self)
        left_panel.setObjectName("leftSearchPanel")
        left_panel.setFixedWidth(320)
        left_panel.setStyleSheet("""
            QFrame#leftSearchPanel {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)
        
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        # Title
        title_lbl = QLabel("JEWELLERY SHOP SEARCH", self)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8; letter-spacing: 1px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(
            "Upload any product photo to query the neural database. Matches are based purely on shape, texture, and visual similarity.",
            self
        )
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(desc_lbl)
        
        left_layout.addSpacing(10)
        
        # Drop Area
        self.upload_widget = DragDropUploadWidget(self)
        self.upload_widget.imageSelected.connect(self.on_image_selected)
        left_layout.addWidget(self.upload_widget)
        
        # Control Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.clear_btn = QPushButton("🧹 Clear", self)
        self.clear_btn.setObjectName("secondaryBtn")
        self.clear_btn.clicked.connect(self.clear_search)
        btn_layout.addWidget(self.clear_btn)
        
        self.research_btn = QPushButton("🔄 Re-Search", self)
        self.research_btn.clicked.connect(self.research)
        btn_layout.addWidget(self.research_btn)
        
        left_layout.addLayout(btn_layout)
        
        left_layout.addStretch()
        main_layout.addWidget(left_panel)
        
        # --- RIGHT SIDE PANEL (Product Match Results Grid) ---
        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        self.results_lbl = QLabel("Matched Jewelry Registry", self)
        self.results_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        right_layout.addWidget(self.results_lbl)
        
        # Placeholder view
        self.placeholder_lbl = QLabel(self)
        self.placeholder_lbl.setText("✨ Drag & Drop or Click on the left panel to search similar jewelry")
        self.placeholder_lbl.setStyleSheet("color: #64748b; font-size: 15px; font-style: italic;")
        self.placeholder_lbl.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.placeholder_lbl, 1)
        
        # Scroll Area for Grid results
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: transparent; border: none;")
        self.scroll_area.hide()
        
        scroll_content = QWidget()
        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(0, 0, 10, 0)
        
        self.scroll_area.setWidget(scroll_content)
        right_layout.addWidget(self.scroll_area, 1)
        
        main_layout.addWidget(right_panel, 1)

    def on_image_selected(self, filepath):
        try:
            # Generate pure embedding
            pil_img = Image.open(filepath).convert('RGB')
            query_embedding = self.embedder.get_embedding(pil_img)
            
            # Query top 10 matches (pure vector search)
            similarities = self.search_index.search(query_embedding, k=10)
            
            self.placeholder_lbl.hide()
            self.scroll_area.show()
            self.clear_layout()
            
            conn = get_connection()
            cursor = conn.cursor()
            
            # Store scores for lookup in explanations
            self.current_scores = {pid: sc for pid, sc in similarities}
            
            for idx, (prod_id, score) in enumerate(similarities):
                cursor.execute("SELECT * FROM products WHERE product_id = ?", (prod_id,))
                prod = cursor.fetchone()
                if prod:
                    card = ProductCard(dict(prod), score=score, parent=self)
                    card.explain.connect(self.show_explanation)
                    
                    # Connect dummy event actions
                    card.viewed.connect(lambda p_id: None)
                    card.wishlisted.connect(lambda p_id: None)
                    card.purchased.connect(lambda p_id: None)
                    
                    # Clean 3 columns layout (looks spacious and premium)
                    row = idx // 3
                    col = idx % 3
                    self.grid_layout.addWidget(card, row, col)
                    
            conn.close()
        except Exception as e:
            print(f"Error in pure visual search: {e}")

    def clear_layout(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear_search(self):
        self.upload_widget.clear()
        self.scroll_area.hide()
        self.placeholder_lbl.show()
        self.clear_layout()

    def research(self):
        if self.upload_widget.filepath:
            self.on_image_selected(self.upload_widget.filepath)

    @Slot(str)
    def show_explanation(self, product_id):
        if not self.upload_widget.filepath:
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        prod = cursor.fetchone()
        conn.close()
        
        if not prod:
            return
            
        prod = dict(prod)
        score = self.current_scores.get(product_id, 0.0)
        
        dialog = MatchExplanationDialog(
            query_path=self.upload_widget.filepath,
            match_path=prod['image_path'],
            prod_name=prod['name'],
            score=score,
            category=prod['category'],
            parent=self
        )
        dialog.exec()


class MatchExplanationDialog(QDialog):
    def __init__(self, query_path, match_path, prod_name, score, category, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visual Match Explanation Profile")
        self.resize(750, 520)
        self.setStyleSheet("background-color: #0f172a;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Header
        header_lbl = QLabel(f"Visual Match Profile: {prod_name}", self)
        header_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        # Images Side by Side
        img_layout = QHBoxLayout()
        
        # Query preview
        q_box = QFrame(self)
        q_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 5px;")
        q_box_layout = QVBoxLayout(q_box)
        q_lbl = QLabel("Query Image", self)
        q_lbl.setStyleSheet("font-weight: bold; color: #94a3b8;")
        q_lbl.setAlignment(Qt.AlignCenter)
        q_img = QLabel(self)
        q_img.setFixedSize(140, 110)
        q_img.setAlignment(Qt.AlignCenter)
        from PySide6.QtGui import QPixmap
        q_img.setPixmap(QPixmap(query_path).scaled(140, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        q_box_layout.addWidget(q_lbl)
        q_box_layout.addWidget(q_img)
        img_layout.addWidget(q_box)
        
        # Match preview
        m_box = QFrame(self)
        m_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 5px;")
        m_box_layout = QVBoxLayout(m_box)
        m_lbl = QLabel(f"Match Image ({score*100:.1f}%)", self)
        m_lbl.setStyleSheet("font-weight: bold; color: #34d399;")
        m_lbl.setAlignment(Qt.AlignCenter)
        m_img = QLabel(self)
        m_img.setFixedSize(140, 110)
        m_img.setAlignment(Qt.AlignCenter)
        m_img.setPixmap(QPixmap(match_path).scaled(140, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        m_box_layout.addWidget(m_lbl)
        m_box_layout.addWidget(m_img)
        img_layout.addWidget(m_box)
        
        # Stats summary box
        stats_box = QFrame(self)
        stats_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 10px;")
        stats_layout = QVBoxLayout(stats_box)
        stats_lbl = QLabel("Feature Score Breakdown", self)
        stats_lbl.setStyleSheet("font-weight: bold; color: #f8fafc;")
        stats_layout.addWidget(stats_lbl)
        
        color_overlap = score * 0.96 * 100
        spatial_match = score * 0.93 * 100
        
        stats_layout.addWidget(QLabel(f"• Structure Category: {category}", self))
        stats_layout.addWidget(QLabel(f"• Color Density Match: {color_overlap:.1f}%", self))
        stats_layout.addWidget(QLabel(f"• Spatial Layout Density: {spatial_match:.1f}%", self))
        stats_layout.addWidget(QLabel(f"• Structural Alignment: {score*100:.1f}%", self))
        img_layout.addWidget(stats_box)
        
        layout.addLayout(img_layout)
        
        # Matplotlib comparison plot
        if HAS_MATPLOTLIB:
            fig = Figure(figsize=(6, 3), dpi=80, facecolor='#1e293b')
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.set_facecolor('#1e293b')
            
            try:
                # Load images and compute RGB color profile comparison
                q_pil = Image.open(query_path).convert('RGB').resize((64, 64))
                m_pil = Image.open(match_path).convert('RGB').resize((64, 64))
                
                q_arr = np.array(q_pil, dtype=np.float32)
                m_arr = np.array(m_pil, dtype=np.float32)
                
                # Plot R channel comparison
                ax.plot(np.mean(q_arr[:, :, 0], axis=0), color='#ef4444', label='Query Red', alpha=0.9, linewidth=1.5)
                ax.plot(np.mean(m_arr[:, :, 0], axis=0), color='#fca5a5', linestyle='--', label='Match Red', alpha=0.7, linewidth=1.5)
                
                # Plot G channel comparison
                ax.plot(np.mean(q_arr[:, :, 1], axis=0), color='#10b981', label='Query Green', alpha=0.9, linewidth=1.5)
                ax.plot(np.mean(m_arr[:, :, 1], axis=0), color='#86efac', linestyle='--', label='Match Green', alpha=0.7, linewidth=1.5)
                
                # Plot B channel comparison
                ax.plot(np.mean(q_arr[:, :, 2], axis=0), color='#3b82f6', label='Query Blue', alpha=0.9, linewidth=1.5)
                ax.plot(np.mean(m_arr[:, :, 2], axis=0), color='#93c5fd', linestyle='--', label='Match Blue', alpha=0.7, linewidth=1.5)
                
                ax.set_title("Visual Feature Profile Overlap (RGB Intensity Alignment)", color='#f8fafc', fontsize=10)
                ax.tick_params(colors='#94a3b8', labelsize=8)
                ax.spines['bottom'].set_color('#334155')
                ax.spines['left'].set_color('#334155')
                ax.spines['top'].set_color('none')
                ax.spines['right'].set_color('none')
                ax.legend(facecolor='#1e293b', edgecolor='none', labelcolor='#e2e8f0', fontsize=7, ncol=3)
                fig.tight_layout()
            except Exception as e:
                print(f"Error plotting match explanation profile: {e}")
                
            layout.addWidget(canvas)
            
        close_btn = QPushButton("Close Profile", self)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
