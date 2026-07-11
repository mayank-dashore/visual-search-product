from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QFrame, QHeaderView, QDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from database.connection import get_connection
import os

class ClickableImageLabel(QLabel):
    clicked = Signal(str, str) # Emits (image_path, product_name)

    def __init__(self, image_path, prod_name, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.prod_name = prod_name
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to enlarge product image")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path, self.prod_name)

class UserProfileTab(QWidget):
    def __init__(self, parent=None, admin_mode=False):
        super().__init__(parent)
        self.user_id = None
        self.admin_mode = admin_mode
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(10)
        
        # Profile Title Card
        self.title_card = QFrame(self)
        self.title_card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 10px;")
        self.title_layout = QVBoxLayout(self.title_card)
        self.title_layout.setContentsMargins(20, 15, 20, 15)
        
        self.name_lbl = QLabel("Customer Profile", self)
        self.name_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #f8fafc;")
        self.title_layout.addWidget(self.name_lbl)
        
        self.type_lbl = QLabel("Tier: Premium Buyer", self)
        self.type_lbl.setStyleSheet("font-size: 13px; color: #38bdf8;")
        self.title_layout.addWidget(self.type_lbl)
        
        # Stats summary layout (Vertically stacked for admin view side-by-side layout, or horizontal)
        self.stats_row_widget = QWidget(self)
        if self.admin_mode:
            stats_layout = QVBoxLayout(self.stats_row_widget)
        else:
            stats_layout = QHBoxLayout(self.stats_row_widget)
            
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        
        self.stats_view = self.create_stat_card("👁️ Views", "0")
        self.stats_click = self.create_stat_card("🖱️ Clicks", "0")
        self.stats_wish = self.create_stat_card("❤️ Wishlist", "0")
        self.stats_buy = self.create_stat_card("🛒 Purchases", "0")
        
        stats_layout.addWidget(self.stats_view)
        stats_layout.addWidget(self.stats_click)
        stats_layout.addWidget(self.stats_wish)
        stats_layout.addWidget(self.stats_buy)
        
        # User Event History Table Header & Widget
        self.table_title = QLabel("Recent Interactions History Log", self)
        self.table_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cbd5e1;")
        if not self.admin_mode:
            self.table_title.setText("My Shopping History")
            
        self.table = QTableWidget(self)
        if self.admin_mode:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["Product Image", "Product Name", "Action Type", "Timestamp", "Dwell Time (s)"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        else:
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(["Product Image", "Product Name", "Action Type", "Date"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Split layout into side-by-side if admin mode
        if self.admin_mode:
            # Main horizontal splitter container
            split_widget = QWidget(self)
            split_layout = QHBoxLayout(split_widget)
            split_layout.setContentsMargins(0, 0, 0, 0)
            split_layout.setSpacing(15)
            
            # Left panel
            left_panel = QWidget(split_widget)
            left_layout = QVBoxLayout(left_panel)
            left_layout.setContentsMargins(0, 0, 0, 0)
            left_layout.setSpacing(12)
            left_layout.addWidget(self.title_card)
            left_layout.addWidget(self.stats_row_widget)
            left_layout.addStretch()
            left_panel.setFixedWidth(280) # Fixed width for left metadata panel
            
            # Right panel
            right_panel = QWidget(split_widget)
            right_layout = QVBoxLayout(right_panel)
            right_layout.setContentsMargins(0, 0, 0, 0)
            right_layout.setSpacing(8)
            right_layout.addWidget(self.table_title)
            right_layout.addWidget(self.table)
            
            split_layout.addWidget(left_panel)
            split_layout.addWidget(right_panel, 1)
            
            self.main_layout.addWidget(split_widget)
        else:
            # Customer mode: just normal vertical stack
            self.title_card.setVisible(False)
            self.stats_row_widget.setVisible(False)
            self.main_layout.addWidget(self.table_title)
            self.main_layout.addWidget(self.table)

    def create_stat_card(self, title, val):
        card = QFrame(self)
        card.setFixedSize(160, 80)
        card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #38bdf8;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)
        
        title_lbl = QLabel(title, card)
        title_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; border: none; background: transparent;")
        title_lbl.setAlignment(Qt.AlignCenter)
        
        val_lbl = QLabel(val, card)
        val_lbl.setStyleSheet("color: #f8fafc; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        val_lbl.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        
        # Keep a reference to the value label to update it later
        card.val_lbl = val_lbl
        return card

    def set_user(self, user_id):
        self.user_id = user_id
        self.refresh_profile()

    def refresh_profile(self):
        if not self.user_id:
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        
        # Load user info (Only in admin view mode)
        if self.admin_mode:
            cursor.execute("SELECT name, profile_type FROM users WHERE user_id = ?", (self.user_id,))
            user_row = cursor.fetchone()
            if user_row:
                self.name_lbl.setText(user_row['name'])
                self.type_lbl.setText(f"Tier Profile: {user_row['profile_type']}")
                
            # Get count stats (only for products that exist in the active catalog)
            stats = {}
            for etype in ['view', 'click', 'wishlist', 'purchase']:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM user_events 
                    JOIN products ON user_events.product_id = products.product_id 
                    WHERE user_id = ? AND event_type = ?
                """, (self.user_id, etype))
                stats[etype] = str(cursor.fetchone()[0])
                
            self.stats_view.val_lbl.setText(stats['view'])
            self.stats_click.val_lbl.setText(stats['click'])
            self.stats_wish.val_lbl.setText(stats['wishlist'])
            self.stats_buy.val_lbl.setText(stats['purchase'])
        
        # Load interaction history table
        cursor.execute("""
            SELECT image_path, name, event_type, timestamp, dwell_time 
            FROM user_events 
            JOIN products ON user_events.product_id = products.product_id
            WHERE user_id = ? 
            ORDER BY timestamp DESC
            LIMIT 50
        """, (self.user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            # 0. Product Image Thumbnail (Clickable to Enlarge)
            img_path = row['image_path']
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            actual_img_path = img_path
            if img_path and not os.path.isabs(img_path):
                clean_path = img_path
                if img_path.startswith("visual_search_engine/"):
                    clean_path = img_path[len("visual_search_engine/"):]
                elif img_path.startswith("visual_search_engine\\"):
                    clean_path = img_path[len("visual_search_engine\\"):]
                actual_img_path = os.path.join(app_root, clean_path)
                
            img_lbl = ClickableImageLabel(actual_img_path, row['name'], self)
            img_lbl.setAlignment(Qt.AlignCenter)
            if actual_img_path and os.path.exists(actual_img_path):
                pix = QPixmap(actual_img_path)
                img_lbl.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("💍")
                img_lbl.setStyleSheet("color: #64748b; font-size: 14px;")
            
            img_lbl.clicked.connect(self.show_enlarged_image)
            self.table.setCellWidget(row_idx, 0, img_lbl)
            
            # 1. Product Name
            self.table.setItem(row_idx, 1, QTableWidgetItem(row['name']))
            
            if self.admin_mode:
                # 2. Action Type
                self.table.setItem(row_idx, 2, QTableWidgetItem(row['event_type'].capitalize()))
                # 3. Timestamp
                self.table.setItem(row_idx, 3, QTableWidgetItem(row['timestamp']))
                # 4. Dwell Time
                self.table.setItem(row_idx, 4, QTableWidgetItem(str(row['dwell_time'])))
                
                # Align center for text columns
                for col in [2, 3, 4]:
                    self.table.item(row_idx, col).setTextAlignment(Qt.AlignCenter)
            else:
                # 2. Action Type
                self.table.setItem(row_idx, 2, QTableWidgetItem(row['event_type'].capitalize()))
                self.table.item(row_idx, 2).setTextAlignment(Qt.AlignCenter)
                # 3. Date when they did that (using timestamp)
                self.table.setItem(row_idx, 3, QTableWidgetItem(row['timestamp']))
                self.table.item(row_idx, 3).setTextAlignment(Qt.AlignCenter)
                
            self.table.setRowHeight(row_idx, 45)

    def show_enlarged_image(self, image_path, prod_name):
        if not image_path or not os.path.exists(image_path):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Product Preview - {prod_name}")
        dialog.resize(500, 500)
        dialog.setStyleSheet("background-color: #0f172a;")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(15, 15, 15, 15)
        
        lbl = QLabel(dialog)
        lbl.setAlignment(Qt.AlignCenter)
        pix = QPixmap(image_path)
        lbl.setPixmap(pix.scaled(470, 470, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(lbl)
        
        dialog.exec()
