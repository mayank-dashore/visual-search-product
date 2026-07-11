from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from gui.customer_view import CustomerViewTab
from gui.admin_view import AdminViewTab
from gui.visual_search_tab import PureVisualSearchTab
from gui.components import STYLESHEET

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-Powered Visual Search & Recommendation Engine")
        self.resize(1150, 780)
        
        # Apply CSS style sheet
        self.setStyleSheet(STYLESHEET)
        
        # Main layout wrapper
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Elegant Header Banner
        header = QWidget(self)
        header.setFixedHeight(65)
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border-bottom: 2px solid #0ea5e9;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        title_lbl = QLabel("💎 AURA JEWELRY SUITE", header)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8; background: transparent;")
        header_layout.addWidget(title_lbl)
        
        subtitle_lbl = QLabel("Visual Search & Neural Recommender v1.0", header)
        subtitle_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
        header_layout.addWidget(subtitle_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(header)
        
        # Tabs
        self.tabs = QTabWidget(self)
        self.visual_search_tab = PureVisualSearchTab(self)
        self.customer_tab = CustomerViewTab(self)
        self.admin_tab = AdminViewTab(self)
        
        # Connect tab change to refresh statistics
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        self.tabs.addTab(self.visual_search_tab, "🔍 Visual Search Landing Page")
        self.tabs.addTab(self.customer_tab, "🛍️ Recommender Sandbox")
        self.tabs.addTab(self.admin_tab, "⚙️ Admin Dashboard")
        
        layout.addWidget(self.tabs)
        
    def on_tab_changed(self, index):
        if index == 1:
            # Customer portal active - refresh recommendations
            self.customer_tab.update_recommendations()
            self.customer_tab.update_recently_viewed()
        elif index == 2:
            # Admin portal active - refresh charts and tables
            self.admin_tab.refresh_view()
