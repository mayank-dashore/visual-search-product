from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QFrame, QMessageBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from database.connection import get_connection

class LoginWidget(QWidget):
    # Signals
    login_successful = Signal(str, str) # Emits (user_id, role)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Outer Card Container
        card = QFrame(self)
        card.setObjectName("loginCard")
        card.setFixedSize(400, 480)
        card.setStyleSheet("""
            QFrame#loginCard {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 16px;
            }
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 40, 30, 40)
        card_layout.setSpacing(18)
        
        # Logo/Icon
        logo_lbl = QLabel("💎", card)
        logo_lbl.setStyleSheet("font-size: 54px; margin-bottom: 5px;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(logo_lbl)
        
        # Title
        title_lbl = QLabel("JEWELLERY SHOP", card)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #38bdf8; letter-spacing: 1px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title_lbl)
        
        sub_lbl = QLabel("Sign in to access search & recommendations", card)
        sub_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(sub_lbl)
        
        card_layout.addSpacing(15)
        
        # Account Type Selection
        role_layout = QVBoxLayout()
        role_layout.setSpacing(5)
        role_lbl = QLabel("Login As:", card)
        role_lbl.setStyleSheet("font-weight: bold; color: #cbd5e1; font-size: 12px;")
        role_layout.addWidget(role_lbl)
        
        self.role_combo = QComboBox(card)
        self.role_combo.addItems(["Customer Portal", "System Administrator"])
        self.role_combo.currentTextChanged.connect(self.on_role_changed)
        role_layout.addWidget(self.role_combo)
        card_layout.addLayout(role_layout)
        
        # User selection Layout
        self.user_layout_widget = QWidget(card)
        user_layout = QVBoxLayout(self.user_layout_widget)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(5)
        
        user_lbl = QLabel("Select Profile:", self.user_layout_widget)
        user_lbl.setStyleSheet("font-weight: bold; color: #cbd5e1; font-size: 12px;")
        user_layout.addWidget(user_lbl)
        
        self.user_combo = QComboBox(self.user_layout_widget)
        self.load_users()
        user_layout.addWidget(self.user_combo)
        card_layout.addWidget(self.user_layout_widget)
        
        # Password Layout (Mocked for administration, empty for customer)
        self.pass_layout_widget = QWidget(card)
        self.pass_layout_widget.hide() # Hidden by default for customers
        pass_layout = QVBoxLayout(self.pass_layout_widget)
        pass_layout.setContentsMargins(0, 0, 0, 0)
        pass_layout.setSpacing(5)
        
        pass_lbl = QLabel("Admin Password:", self.pass_layout_widget)
        pass_lbl.setStyleSheet("font-weight: bold; color: #cbd5e1; font-size: 12px;")
        pass_layout.addWidget(pass_lbl)
        
        self.pass_input = QLineEdit(self.pass_layout_widget)
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setPlaceholderText("Enter admin password (hint: admin)")
        pass_layout.addWidget(self.pass_input)
        card_layout.addWidget(self.pass_layout_widget)
        
        # Sign In Button
        self.login_btn = QPushButton("SIGN IN", card)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 12px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        self.login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(self.login_btn)
        
        main_layout.addWidget(card)

    def load_users(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, profile_type FROM users")
        for user_id, name, ptype in cursor.fetchall():
            self.user_combo.addItem(f"{name} ({ptype})", user_id)
        conn.close()

    def on_role_changed(self, role):
        if role == "System Administrator":
            self.user_layout_widget.hide()
            self.pass_layout_widget.show()
        else:
            self.user_layout_widget.show()
            self.pass_layout_widget.hide()

    def handle_login(self):
        role = self.role_combo.currentText()
        if role == "System Administrator":
            password = self.pass_input.text()
            if password == "admin":
                self.login_successful.emit("admin_1", "admin")
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect Administrator password!")
        else:
            idx = self.user_combo.currentIndex()
            if idx >= 0:
                user_id = self.user_combo.itemData(idx)
                self.login_successful.emit(user_id, "customer")
            else:
                QMessageBox.warning(self, "Error", "No user profile selected!")
