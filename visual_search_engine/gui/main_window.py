from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QLabel, QHBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Qt, Slot
from gui.customer_view import CustomerViewTab
from gui.admin_view import AdminViewTab
from gui.visual_search_tab import PureVisualSearchTab
from gui.user_profile_tab import UserProfileTab
from gui.login_widget import LoginWidget
from gui.components import STYLESHEET

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI-Powered Visual Search & Recommendation Engine")
        self.resize(1150, 780)
        
        # Apply CSS style sheet
        self.setStyleSheet(STYLESHEET)
        
        # Start in Login State
        self.show_login_screen()

    def show_login_screen(self):
        self.login_widget = LoginWidget(self)
        self.login_widget.login_successful.connect(self.on_login_successful)
        self.setCentralWidget(self.login_widget)

    @Slot(str, str)
    def on_login_successful(self, user_id, role):
        # Setup main dashboard layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Elegant Header Banner
        header = QFrame(self)
        header.setFixedHeight(65)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border-bottom: 2px solid #0ea5e9;
                border-radius: 8px;
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        title_lbl = QLabel("💎 JEWELLERY SHOP", header)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8; background: transparent;")
        header_layout.addWidget(title_lbl)
        
        # User details + Logout on Right
        right_header_layout = QHBoxLayout()
        right_header_layout.setSpacing(15)
        
        if role == "admin":
            user_lbl_text = "👮 System Administrator"
        else:
            user_lbl_text = f"👤 User: {user_id}"
            
        user_lbl = QLabel(user_lbl_text, header)
        user_lbl.setStyleSheet("font-size: 13px; color: #f8fafc; font-weight: bold; background: transparent;")
        right_header_layout.addWidget(user_lbl)
        
        logout_btn = QPushButton("🚪 Logout", header)
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: #f43f5e;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e11d48;
            }
        """)
        logout_btn.clicked.connect(self.logout)
        right_header_layout.addWidget(logout_btn)
        
        header_layout.addLayout(right_header_layout)
        layout.addWidget(header)
        
        # Dynamic tab widget loading based on role
        self.tabs = QTabWidget(self)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        if role == "customer":
            self.visual_search_tab = PureVisualSearchTab(self)
            self.customer_tab = CustomerViewTab(self)
            self.profile_tab = UserProfileTab(self)
            
            # Set user context
            self.customer_tab.set_user(user_id)
            self.profile_tab.set_user(user_id)
            
            self.tabs.addTab(self.visual_search_tab, "🔍 Visual Search Landing Page")
            self.tabs.addTab(self.customer_tab, "🛍️ Recommender Sandbox")
            self.tabs.addTab(self.profile_tab, "👤 My Profile & Logs")
        else:
            self.admin_tab = AdminViewTab(self)
            self.tabs.addTab(self.admin_tab, "⚙️ Admin Dashboard & Controls")
            
        layout.addWidget(self.tabs)

    def logout(self):
        # Clear widgets and return to login
        self.show_login_screen()

    def on_tab_changed(self, index):
        # Dynamically refresh tab states when switching
        tab_text = self.tabs.tabText(index)
        if "Recommender Sandbox" in tab_text:
            self.customer_tab.update_recommendations()
            self.customer_tab.update_recently_viewed()
        elif "My Profile & Logs" in tab_text:
            self.profile_tab.refresh_profile()
        elif "Admin Dashboard" in tab_text:
            self.admin_tab.refresh_view()
