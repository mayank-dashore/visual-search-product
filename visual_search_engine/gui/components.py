from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QColor, QPalette
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
            self.btn_explain = QPushButton("🔍 Explain Match", self)
            self.btn_explain.clicked.connect(lambda: self.explain.emit(self.product_id))
            btn_layout.addWidget(self.btn_explain)
        else:
            self.btn_view = QPushButton("👁️", self)
            self.btn_view.setToolTip("View Product Details")
            self.btn_view.setObjectName("secondaryBtn")
            self.btn_view.clicked.connect(lambda: self.viewed.emit(self.product_id))
            
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
