from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QLineEdit, QComboBox, QFileDialog, QFormLayout, 
                             QGroupBox, QHeaderView, QMessageBox)
from PySide6.QtCore import Qt
from database.connection import get_connection
from utils.data_generator import rebuild_vector_search_index
from models.embedder import EmbeddingGenerator
from retrieval.search_index import SearchIndex
from PIL import Image
import os

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

class MplCanvas(QWidget):
    """A canvas to display Matplotlib charts."""
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        super().__init__(parent)
        if HAS_MATPLOTLIB:
            self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#1e293b')
            self.canvas = FigureCanvas(self.fig)
            self.axes = self.fig.add_subplot(111)
            self.axes.set_facecolor('#1e293b')
            
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.canvas)
        else:
            layout = QVBoxLayout(self)
            lbl = QLabel("Chart (Install matplotlib to display analytics visually)", self)
            lbl.setStyleSheet("color: #64748b; font-style: italic;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)

    def plot_bar(self, categories, values, title):
        if not HAS_MATPLOTLIB:
            return
        self.axes.clear()
        self.axes.bar(categories, values, color=['#38bdf8', '#34d399', '#f43f5e', '#a855f7'], width=0.5)
        self.axes.set_title(title, color='#f8fafc', fontsize=11, fontweight='bold', pad=10)
        self.axes.tick_params(colors='#94a3b8', labelsize=9)
        
        # Grid
        self.axes.grid(True, color='#334155', linestyle='--', alpha=0.5)
        self.axes.spines['bottom'].set_color('#334155')
        self.axes.spines['top'].set_color('none')
        self.axes.spines['right'].set_color('none')
        self.axes.spines['left'].set_color('#334155')
        
        # Optimize spacing to prevent cut-off labels
        self.fig.tight_layout()
        self.canvas.draw()


class AdminViewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.embedder = EmbeddingGenerator()
        self.search_index = SearchIndex(dimension=self.embedder.get_dim())
        self.search_index.load()
        self.selected_img_path = None
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Left Panel (Controls & Add Product Form)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)
        
        # System Actions Group
        sys_group = QGroupBox("System Controls", self)
        sys_group.setStyleSheet("QGroupBox { color: #f8fafc; font-weight: bold; border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
        sys_layout = QVBoxLayout(sys_group)
        
        self.rebuild_btn = QPushButton("🔄 Rebuild FAISS Vector Index", self)
        self.rebuild_btn.clicked.connect(self.on_rebuild_index)
        sys_layout.addWidget(self.rebuild_btn)
        
        self.stats_lbl = QLabel(self)
        self.stats_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; margin-top: 10px;")
        sys_layout.addWidget(self.stats_lbl)
        
        left_layout.addWidget(sys_group)
        
        # Add Product Group
        add_group = QGroupBox("Add New Jewelry Product", self)
        add_group.setStyleSheet("QGroupBox { color: #f8fafc; font-weight: bold; border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
        
        form_layout = QFormLayout(add_group)
        form_layout.setVerticalSpacing(10)
        
        self.name_input = QLineEdit(self)
        form_layout.addRow(QLabel("Product Name:", self), self.name_input)
        
        self.cat_combo = QComboBox(self)
        self.cat_combo.addItems(["Rings", "Necklaces", "Earrings", "Bangles"])
        form_layout.addRow(QLabel("Category:", self), self.cat_combo)
        
        self.price_input = QLineEdit(self)
        form_layout.addRow(QLabel("Price ($):", self), self.price_input)
        
        self.stock_input = QLineEdit(self)
        form_layout.addRow(QLabel("Stock Level:", self), self.stock_input)
        
        # Image uploader line
        img_row = QHBoxLayout()
        self.img_path_lbl = QLabel("No image selected", self)
        self.img_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.browse_btn = QPushButton("Browse Image...", self)
        self.browse_btn.setObjectName("secondaryBtn")
        self.browse_btn.clicked.connect(self.on_browse_image)
        img_row.addWidget(self.img_path_lbl)
        img_row.addWidget(self.browse_btn)
        
        form_layout.addRow(QLabel("Image file:", self), img_row)
        
        self.add_btn = QPushButton("Add & Embed Product", self)
        self.add_btn.clicked.connect(self.on_add_product)
        form_layout.addRow(self.add_btn)
        
        left_layout.addWidget(add_group)
        
        # Canvas for charts
        self.chart_canvas = MplCanvas(self, width=4, height=3)
        self.chart_canvas.setMinimumHeight(240)
        left_layout.addWidget(self.chart_canvas)
        
        main_layout.addLayout(left_layout, 1)
        
        # Right Panel (Product Grid Table)
        right_layout = QVBoxLayout()
        
        table_title = QLabel("Product Directory & Vector Registry", self)
        table_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        right_layout.addWidget(table_title)
        
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Category", "Price", "Stock"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        right_layout.addWidget(self.table)
        
        main_layout.addLayout(right_layout, 2)
        
        # Seed initial content
        self.refresh_view()

    def refresh_view(self):
        self.load_products_table()
        self.update_stats()
        self.update_charts()

    def update_stats(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        n_prod = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        n_user = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM user_events")
        n_event = cursor.fetchone()[0]
        conn.close()
        
        self.stats_lbl.setText(
            f"Database Metrics:\n"
            f"• Registered Products: {n_prod}\n"
            f"• Active Customers: {n_user}\n"
            f"• User Event Traces: {n_event}"
        )

    def update_charts(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT event_type, COUNT(*) FROM user_events GROUP BY event_type")
        rows = cursor.fetchall()
        conn.close()
        
        categories = [r[0].capitalize() for r in rows]
        counts = [r[1] for r in rows]
        
        if not categories:
            categories = ["View", "Click", "Wishlist", "Purchase"]
            counts = [0, 0, 0, 0]
            
        self.chart_canvas.plot_bar(categories, counts, "User Interactions Volume")

    def load_products_table(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, name, category, price, stock FROM products ORDER BY rowid DESC")
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if col_idx in [0, 3, 4]:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

    def on_browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Product Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.selected_img_path = file_path
            self.img_path_lbl.setText(os.path.basename(file_path))

    def on_add_product(self):
        name = self.name_input.text().strip()
        category = self.cat_combo.currentText()
        price_str = self.price_input.text().strip()
        stock_str = self.stock_input.text().strip()
        
        if not name or not price_str or not stock_str or not self.selected_img_path:
            QMessageBox.warning(self, "Validation Error", "All fields including product image must be completed!")
            return
            
        try:
            price = float(price_str)
            stock = int(stock_str)
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Price and Stock must be numeric values!")
            return
            
        # Add to Database
        conn = get_connection()
        cursor = conn.cursor()
        prod_id = f"prod_{category[0].lower()}_{os.urandom(4).hex()}"
        
        try:
            cursor.execute(
                "INSERT INTO products (product_id, name, category, price, image_path, stock) VALUES (?, ?, ?, ?, ?, ?)",
                (prod_id, name, category, price, self.selected_img_path, stock)
            )
            conn.commit()
            
            # Generate embedding & Add to search index immediately
            pil_img = Image.open(self.selected_img_path).convert('RGB')
            emb = self.embedder.get_embedding(pil_img)
            
            # Add to search index
            self.search_index.load()
            self.search_index.add_product(prod_id, emb)
            self.search_index.save()
            
            QMessageBox.information(self, "Success", f"Product '{name}' successfully inserted and index updated.")
            
            # Clear inputs
            self.name_input.clear()
            self.price_input.clear()
            self.stock_input.clear()
            self.img_path_lbl.setText("No image selected")
            self.selected_img_path = None
            
            self.refresh_view()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add product: {e}")
        finally:
            conn.close()

    def on_rebuild_index(self):
        self.rebuild_btn.setEnabled(False)
        self.rebuild_btn.setText("Processing Vector Embeddings...")
        try:
            rebuild_vector_search_index()
            self.search_index.load()
            QMessageBox.information(self, "Success", "Vector search index rebuilt successfully.")
            self.refresh_view()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to rebuild index: {e}")
        finally:
            self.rebuild_btn.setEnabled(True)
            self.rebuild_btn.setText("🔄 Rebuild FAISS Vector Index")
