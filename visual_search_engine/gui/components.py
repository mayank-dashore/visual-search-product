from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSizePolicy, QDialog, QWidget)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QColor, QPalette
from database.connection import get_connection
import os

# Modern dark theme stylesheet
STYLESHEET = """
QMainWindow {
    background-color: #0f172a;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0f172a;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 10px 20px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #0f172a;
    color: #38bdf8;
    border-bottom: 2px solid #0ea5e9;
}
QTabBar::tab:hover {
    background-color: #334155;
    color: #f8fafc;
}
QFrame {
    border: none;
}
QLabel {
    color: #e2e8f0;
    font-family: "Segoe UI", Roboto, Helvetica;
}
QLineEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    padding: 8px 12px;
}
QLineEdit:focus {
    border: 1px solid #38bdf8;
}
QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    padding: 8px 12px;
    min-width: 150px;
}
QComboBox:focus {
    border: 1px solid #38bdf8;
}
QPushButton {
    background-color: #0ea5e9;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
}
QPushButton:hover {
    background-color: #0284c7;
}
QPushButton:pressed {
    background-color: #0369a1;
}
QPushButton#secondaryBtn {
    background-color: #334155;
    color: #cbd5e1;
}
QPushButton#secondaryBtn:hover {
    background-color: #475569;
}
QTableWidget {
    background-color: #1e293b;
    color: #e2e8f0;
    gridline-color: #334155;
    border: 1px solid #334155;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #334155;
    color: #f8fafc;
    padding: 6px;
    border: 1px solid #1e293b;
}
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
"""

class DragDropUploadWidget(QFrame):
    imageSelected = Signal(str) # Emits the filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.filepath = None
        self.setMinimumSize(250, 180)
        
        # UI design
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #334155;
                border-radius: 12px;
                background-color: #1e293b;
            }
            QFrame:hover {
                border-color: #38bdf8;
                background-color: #0f172a;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        self.icon_label = QLabel("📥", self)
        self.icon_label.setStyleSheet("font-size: 36px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("Drag & Drop Jewelry Image Here\nor Click to Upload", self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet("color: #94a3b8; font-size: 13px; font-weight: 500;")
        layout.addWidget(self.text_label)
        
        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.hide()
        layout.addWidget(self.preview_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Jewelry Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if file_path:
                self.set_image(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    border: 2px dashed #38bdf8;
                    border-radius: 12px;
                    background-color: #0f172a;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #334155;
                border-radius: 12px;
                background-color: #1e293b;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.exists(file_path) and file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.set_image(file_path)
                event.acceptProposedAction()

    def set_image(self, filepath):
        self.filepath = filepath
        self.icon_label.hide()
        self.text_label.hide()
        
        pixmap = QPixmap(filepath)
        scaled_pixmap = pixmap.scaled(200, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)
        self.preview_label.show()
        
        self.imageSelected.emit(filepath)
        
    def clear(self):
        self.filepath = None
        self.preview_label.hide()
        self.icon_label.show()
        self.text_label.show()


class ProductCard(QFrame):
    # Signals for simulation
    viewed = Signal(str)     # product_id
    clicked = Signal(str)    # product_id
    wishlisted = Signal(str) # product_id
    purchased = Signal(str)  # product_id
    explain = Signal(str)    # product_id

    def __init__(self, product, score=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.product_id = product['product_id']
        
        self.setMinimumSize(180, 260)
        self.setMaximumWidth(220)
        
        # Sleek design stylesheet
        self.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 10px;
            }
            QFrame#cardFrame:hover {
                border-color: #38bdf8;
                background-color: #2c3a50;
            }
        """)
        
        self.setObjectName("cardFrame")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Image
        self.image_lbl = QLabel(self)
        self.image_lbl.setFixedSize(164, 130)
        self.image_lbl.setAlignment(Qt.AlignCenter)
        self.image_lbl.setStyleSheet("border-radius: 6px; background-color: #0f172a;")
        
        if os.path.exists(product['image_path']):
            pixmap = QPixmap(product['image_path'])
            self.image_lbl.setPixmap(pixmap.scaled(164, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_lbl.setText("💍 No Image")
            self.image_lbl.setStyleSheet("color: #64748b; border-radius: 6px; background-color: #0f172a;")
            
        layout.addWidget(self.image_lbl)
        
        # Title & Category
        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        
        name_lbl = QLabel(product['name'], self)
        name_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #f8fafc;")
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumHeight(35)
        title_layout.addWidget(name_lbl)
        
        cat_lbl = QLabel(f"{product['category']} • ${product['price']:.2f}", self)
        cat_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        title_layout.addWidget(cat_lbl)
        
        if score is not None:
            score_lbl = QLabel(f" Match: {score*100:.1f}% ", self)
            score_lbl.setStyleSheet("color: #34d399; font-size: 10px; font-weight: bold; background-color: #064e3b; border-radius: 4px; padding: 2px 4px;")
            score_lbl.setFixedWidth(80)
            score_lbl.setAlignment(Qt.AlignCenter)
            title_layout.addWidget(score_lbl)
            
        layout.addLayout(title_layout)
        layout.addStretch()
        
        # Action Buttons (Event Simulators or Explain Match)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        if score is not None:
            self.score = score
            self.btn_explain = QPushButton("🔍 Explain Match", self)
            self.btn_explain.clicked.connect(self.show_details)
            btn_layout.addWidget(self.btn_explain)
        else:
            self.btn_view = QPushButton("👁️", self)
            self.btn_view.setToolTip("View Product Details")
            self.btn_view.setObjectName("secondaryBtn")
            self.btn_view.clicked.connect(self.on_view_clicked)
            
            self.btn_wish = QPushButton("❤️", self)
            self.btn_wish.setToolTip("Add to Wishlist")
            self.btn_wish.setObjectName("secondaryBtn")
            self.btn_wish.clicked.connect(lambda: self.wishlisted.emit(self.product_id))
            
            self.btn_buy = QPushButton("🛒 Buy", self)
            self.btn_buy.setToolTip("Purchase Product")
            self.btn_buy.clicked.connect(lambda: self.purchased.emit(self.product_id))
            
            btn_layout.addWidget(self.btn_view)
            btn_layout.addWidget(self.btn_wish)
            btn_layout.addWidget(self.btn_buy)
        
        layout.addLayout(btn_layout)

    def on_view_clicked(self):
        self.viewed.emit(self.product_id)
        self.show_details()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.show_details()

    def show_details(self):
        # Determine current user ID if available
        user_id = None
        p = self.parent()
        while p:
            if hasattr(p, "current_user_id"):
                user_id = p.current_user_id
                break
            p = p.parent()
            
        dialog = ProductDetailsDialog(
            product=self.product,
            score=getattr(self, "score", None),
            user_id=user_id,
            parent=self
        )
        dialog.exec()


class ProductDetailsDialog(QDialog):
    def __init__(self, product, score=None, user_id=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.score = score
        self.user_id = user_id
        
        self.setWindowTitle(f"Product Details - {product['name']}")
        self.resize(600, 500)
        self.setStyleSheet("background-color: #0f172a;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Upper Layout (Image and Meta)
        upper_layout = QHBoxLayout()
        upper_layout.setSpacing(20)
        
        # Image (Enlarged)
        img_lbl = QLabel(self)
        img_lbl.setFixedSize(240, 200)
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setStyleSheet("border-radius: 8px; background-color: #1e293b; border: 1px solid #334155;")
        if os.path.exists(product['image_path']):
            pix = QPixmap(product['image_path'])
            img_lbl.setPixmap(pix.scaled(240, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img_lbl.setText("💍 No Image")
        upper_layout.addWidget(img_lbl)
        
        # Meta info
        meta_widget = QWidget(self)
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(10)
        
        name_lbl = QLabel(product['name'], self)
        name_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        name_lbl.setWordWrap(True)
        meta_layout.addWidget(name_lbl)
        
        cat_lbl = QLabel(f"Category: {product['category']}", self)
        cat_lbl.setStyleSheet("color: #38bdf8; font-size: 13px;")
        meta_layout.addWidget(cat_lbl)
        
        price_lbl = QLabel(f"Price: ${product['price']:.2f}", self)
        price_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #34d399;")
        meta_layout.addWidget(price_lbl)
        
        stock_lbl = QLabel(f"Available Stock: {product['stock']} units", self)
        stock_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        meta_layout.addWidget(stock_lbl)
        
        meta_layout.addStretch()
        upper_layout.addWidget(meta_widget, 1)
        layout.addLayout(upper_layout)
        
        # Explanation Section
        explain_box = QFrame(self)
        explain_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px;")
        explain_layout = QVBoxLayout(explain_box)
        explain_layout.setSpacing(8)
        
        exp_title = QLabel("🤖 AI Recommendation & Match Profile", self)
        exp_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        explain_layout.addWidget(exp_title)
        
        if score is not None:
            cf_factor = 40.0 * score
            content_factor = 20.0
            popularity_factor = 10.0
            
            # Query category profile to explain content match
            if user_id:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM user_events WHERE user_id = ? AND product_id IN (SELECT product_id FROM products WHERE category = ?)",
                        (user_id, product['category'])
                    )
                    cat_event_count = cursor.fetchone()[0]
                    conn.close()
                    if cat_event_count > 0:
                        content_factor = min(20.0, 5.0 + 2.0 * cat_event_count)
                except Exception:
                    pass
            
            explain_layout.addWidget(QLabel(f"• Overall Matching Score: {score*100:.1f}%", self))
            explain_layout.addWidget(QLabel(f"  - Collaborative Filtering: {cf_factor:.1f}% (Based on similar buyers' tastes)", self))
            explain_layout.addWidget(QLabel(f"  - Category Affinity: {content_factor:.1f}% (Matches your preference for {product['category']})", self))
            explain_layout.addWidget(QLabel(f"  - Stock & Popularity: {popularity_factor:.1f}% (Based on general shopper clicks)", self))
            
            # Detailed visual explain hint if it's visual search tab
            if "PureVisualSearchTab" in parent.parent().__class__.__name__:
                explain_layout.addWidget(QLabel(f"  - Visual Core Similarity: {score*100:.1f}% (Matches shape/color profile)", self))
        else:
            explain_layout.addWidget(QLabel("No active recommendation score calculated (Direct catalog search).", self))
            explain_layout.addWidget(QLabel("This product is cataloged in the shop inventory.", self))
            
        layout.addWidget(explain_box)
        
        # Close button
        close_btn = QPushButton("Close Details", self)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
