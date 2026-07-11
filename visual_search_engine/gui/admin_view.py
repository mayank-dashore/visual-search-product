from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QLineEdit, QComboBox, QFileDialog, QFormLayout, 
                             QGroupBox, QHeaderView, QMessageBox, QTabWidget, QFrame, QScrollArea,
                             QCheckBox, QDateEdit, QDialog, QInputDialog)
from PySide6.QtCore import Qt, QTimer, QDate, QSize, QThread, Signal
from PySide6.QtGui import QPixmap
from database.connection import get_connection
from utils.data_generator import rebuild_vector_search_index
from models.embedder import EmbeddingGenerator
from retrieval.search_index import SearchIndex
from PIL import Image
from gui.user_profile_tab import UserProfileTab
import os
import shutil
import numpy as np
import sqlite3

try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
def parse_price_stock_from_filename(filename):
    import re
    import os
    name_part = os.path.splitext(filename)[0]
    parts = re.split(r'[-_]', name_part)
    
    price = None
    stock = None
    
    numeric_parts = []
    for p in parts:
        p_clean = p.replace('$', '').strip()
        if re.match(r'^\d+(\.\d+)?$', p_clean):
            numeric_parts.append(float(p_clean))
            
    if len(numeric_parts) >= 2:
        stock = int(numeric_parts[-1])
        price = round(numeric_parts[-2], 2)
    elif len(numeric_parts) == 1:
        price = round(numeric_parts[0], 2)
        stock = 10
        
    if price is None or price <= 0:
        price = 500.00
    if stock is None or stock < 0:
        stock = 10
        
    return price, stock


class DbWorker(QThread):
    finished = Signal(bool, str) # Emits (success, message)
    status_update = Signal(str)  # Emits current status text
    
    def __init__(self, task_type, params=None):
        super().__init__()
        self.task_type = task_type
        self.params = params or {}
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True
        
    def run(self):
        try:
            if self.task_type == "rebuild":
                import time
                start_time = time.time()
                print("[Rebuild Engine] Starting full FAISS Index rebuild...", flush=True)
                self.status_update.emit("Reading catalog database...")
                
                from database.connection import get_connection
                from models.embedder import EmbeddingGenerator
                from retrieval.search_index import SearchIndex
                from PIL import Image
                import os
                
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT product_id, image_path FROM products")
                rows = cursor.fetchall()
                conn.close()
                
                self.status_update.emit("Instantiating CLIP deep models...")
                embedder = self.params.get("embedder")
                if embedder is None:
                    embedder = EmbeddingGenerator()
                search_index = self.params.get("search_index")
                if search_index is None:
                    search_index = SearchIndex(dimension=embedder.get_dim())
                search_index.clear()
                
                self.status_update.emit(f"Catalog loaded ({len(rows)} items). Processing vectors...")
                success_count = 0
                for idx, row in enumerate(rows):
                    if getattr(self, 'is_cancelled', False):
                        print("[Rebuild Engine] Rebuild cancelled by user.", flush=True)
                        self.finished.emit(False, "Cancelled by user")
                        return
                    
                    prod_id = row['product_id']
                    img_path = row['image_path']
                    
                    actual_img_path = img_path
                    if img_path and not os.path.isabs(img_path):
                        clean_path = img_path
                        if img_path.startswith("visual_search_engine/"):
                            clean_path = img_path[len("visual_search_engine/"):]
                        elif img_path.startswith("visual_search_engine\\"):
                            clean_path = img_path[len("visual_search_engine\\"):]
                        actual_img_path = os.path.join(app_root, clean_path)
                        
                    self.status_update.emit(f"Embedding {idx+1}/{len(rows)}: {os.path.basename(actual_img_path) if actual_img_path else ''}")
                    print(f"[Rebuild Engine] Processing embedding {idx+1}/{len(rows)}: {row['image_path']}", flush=True)
                    
                    if not actual_img_path or not os.path.exists(actual_img_path):
                        continue
                        
                    try:
                        pil_img = Image.open(actual_img_path).convert('RGB')
                        emb = embedder.get_embedding(pil_img)
                        search_index.add_product(prod_id, emb)
                        success_count += 1
                    except Exception as e:
                        print(f"Rebuild skip product {prod_id}: {e}")
                        
                if success_count > 0:
                    search_index.save()
                
                elapsed = time.time() - start_time
                print(f"[Rebuild Engine] Rebuild successful. Total items: {success_count} in {elapsed:.1f}s.", flush=True)
                self.finished.emit(True, f"Rebuilt vector index with {success_count} items in {elapsed:.1f}s.")
                
            elif self.task_type == "delete":
                import time
                start_time = time.time()
                from database.connection import get_connection
                import os
                
                products_to_delete = self.params.get("products", [])
                search_index = self.params.get("search_index")
                
                deleted_count = 0
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                conn = get_connection()
                cursor = conn.cursor()
                search_index.load()
                
                for prod_id, name, img_path in products_to_delete:
                    if getattr(self, 'is_cancelled', False):
                        conn.commit()
                        conn.close()
                        self.finished.emit(False, "Cancelled by user")
                        return
                        
                    try:
                        cursor.execute("DELETE FROM products WHERE product_id = ?", (prod_id,))
                        cursor.execute("DELETE FROM user_events WHERE product_id = ?", (prod_id,))
                        
                        # Delete image file from disk absolutely
                        actual_img_path = img_path
                        if img_path and not os.path.isabs(img_path):
                            clean_path = img_path
                            if img_path.startswith("visual_search_engine/"):
                                clean_path = img_path[len("visual_search_engine/"):]
                            elif img_path.startswith("visual_search_engine\\"):
                                clean_path = img_path[len("visual_search_engine\\"):]
                            actual_img_path = os.path.join(app_root, clean_path)
                            
                        if actual_img_path and os.path.exists(actual_img_path):
                            os.remove(actual_img_path)
                            
                        # ONLY remove this particular embedding without full rebuild!
                        search_index.remove_product(prod_id)
                        
                        deleted_count += 1
                    except Exception as e:
                        print(f"WorkerThread Error deleting product {prod_id}: {e}")
                conn.commit()
                conn.close()
                search_index.save()
                
                elapsed = time.time() - start_time
                self.finished.emit(True, f"Successfully deleted {deleted_count} product(s) from dataset/embeddings in {elapsed:.1f}s.")
                
            elif self.task_type == "add":
                import time
                start_time = time.time()
                from database.connection import get_connection
                from PIL import Image
                import os
                
                name = self.params.get("name")
                category = self.params.get("category")
                price = self.params.get("price")
                stock = self.params.get("stock")
                selected_img_path = self.params.get("selected_img_path")
                embedder = self.params.get("embedder")
                search_index = self.params.get("search_index")
                
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                target_dir = os.path.join(app_root, "datasets", "tanishq-jewellery-dataset", category)
                os.makedirs(target_dir, exist_ok=True)
                
                # Convert file name extension to standard .jpg
                base_name = os.path.splitext(os.path.basename(selected_img_path))[0]
                filename = f"{base_name}_{os.urandom(2).hex()}.jpg"
                dest_path = os.path.join(target_dir, filename)
                
                # Load and convert image to standard RGB JPG
                with Image.open(selected_img_path) as img:
                    rgb_img = img.convert('RGB')
                    rgb_img.save(dest_path, "JPEG")
                    
                # Database relative path
                db_img_path = f"visual_search_engine/datasets/tanishq-jewellery-dataset/{category}/{filename}"
                
                conn = get_connection()
                cursor = conn.cursor()
                import hashlib
                norm_path = db_img_path.replace("\\", "/").lower()
                h = hashlib.md5(norm_path.encode('utf-8')).hexdigest()
                prod_id = f"prod_{h[:12]}"
                cursor.execute(
                    "INSERT INTO products (product_id, name, category, price, image_path, stock) VALUES (?, ?, ?, ?, ?, ?)",
                    (prod_id, name, category, price, db_img_path, stock)
                )
                conn.commit()
                conn.close()
                
                # Generate embedding
                pil_img = Image.open(dest_path).convert('RGB')
                emb = embedder.get_embedding(pil_img)
                
                search_index.load()
                search_index.add_product(prod_id, emb)
                search_index.save()
                
                elapsed = time.time() - start_time
                self.finished.emit(True, f"Product '{name}' successfully added and visual search index updated in {elapsed:.1f}s.")
                
            elif self.task_type == "auto_sync":
                import time
                start_time = time.time()
                print("[Sync Engine] Starting manual folder scan synchronization...", flush=True)
                self.status_update.emit("Resolving project dataset paths...")
                from database.connection import get_connection
                from PIL import Image
                import os
                import numpy as np
                
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                dataset_root = os.path.join(app_root, "datasets", "tanishq-jewellery-dataset")
                
                if not os.path.exists(dataset_root):
                    print(f"[Sync Engine] Dataset root folder not found on disk at: {dataset_root}", flush=True)
                    self.status_update.emit(f"⚠️ Folder not found at: {dataset_root}")
                    self.finished.emit(True, "NO_CHANGES")
                    return
                    
                categories = ["Rings", "Necklaces", "Earrings", "Bangles"]
                
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. Check for deletions
                cursor.execute("SELECT product_id, name, image_path FROM products")
                db_products = cursor.fetchall()
                
                products_deleted = []
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                for p in db_products:
                    if getattr(self, 'is_cancelled', False):
                        print("[Sync Engine] Sync cancelled by user.", flush=True)
                        conn.close()
                        self.finished.emit(False, "Cancelled by user")
                        return
                        
                    img_path = p['image_path']
                    actual_img_path = img_path
                    if img_path and not os.path.isabs(img_path):
                        clean_path = img_path
                        if img_path.startswith("visual_search_engine/"):
                            clean_path = img_path[len("visual_search_engine/"):]
                        elif img_path.startswith("visual_search_engine\\"):
                            clean_path = img_path[len("visual_search_engine\\"):]
                        actual_img_path = os.path.join(app_root, clean_path)
                        
                    if not actual_img_path or not os.path.exists(actual_img_path):
                        products_deleted.append((p['product_id'], p['name']))
                        
                deleted_count = len(products_deleted)
                print(f"[Sync Engine] Found {deleted_count} deleted/missing products on disk.", flush=True)
                
                embedder = self.params.get("embedder")
                search_index = self.params.get("search_index")
                search_index.load()
                
                if products_deleted:
                    for prod_id, name in products_deleted:
                        cursor.execute("DELETE FROM products WHERE product_id = ?", (prod_id,))
                        cursor.execute("DELETE FROM user_events WHERE product_id = ?", (prod_id,))
                        search_index.remove_product(prod_id)
                    conn.commit()
                
                # 2. Check for additions
                cursor.execute("SELECT image_path FROM products")
                existing_paths = {os.path.abspath(row['image_path']).lower() for row in cursor.fetchall()}
                
                files_to_add = []
                for category in categories:
                    cat_dir = os.path.join(dataset_root, category)
                    if not os.path.exists(cat_dir):
                        continue
                    for filename in os.listdir(cat_dir):
                        if getattr(self, 'is_cancelled', False):
                            print("[Sync Engine] Sync cancelled by user.", flush=True)
                            conn.close()
                            self.finished.emit(False, "Cancelled by user")
                            return
                            
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            full_path = os.path.join(cat_dir, filename)
                            if os.path.abspath(full_path).lower() not in existing_paths:
                                files_to_add.append((category, filename, full_path))
                                
                added_count = len(files_to_add)
                print(f"[Sync Engine] Found {added_count} new products to embed/add to DB.", flush=True)
                new_products_found = []
                
                if deleted_count > 0 or added_count > 0:
                    # Add new items to SQLite DB & search index
                    for idx, (category, filename, full_path) in enumerate(files_to_add):
                        if getattr(self, 'is_cancelled', False):
                            print("[Sync Engine] Sync cancelled by user. Rolling back...", flush=True)
                            conn.commit()
                            conn.close()
                            self.finished.emit(False, "Cancelled by user")
                            return
                            
                        import hashlib
                        relative_path = f"visual_search_engine/datasets/tanishq-jewellery-dataset/{category}/{filename}"
                        norm_path = relative_path.replace("\\", "/").lower()
                        h = hashlib.md5(norm_path.encode('utf-8')).hexdigest()
                        prod_id = f"prod_{h[:12]}"
                        name = f"Auto {category[:-1]} - {filename.split('.')[0].split('_')[0].split('-')[0].replace('_', ' ').replace('-', ' ').title()}"
                        price, stock = parse_price_stock_from_filename(filename)
                        
                        try:
                            print(f"[Sync Engine] Embedding new product {idx+1}/{added_count}: {filename}", flush=True)
                            pil_img = Image.open(full_path).convert('RGB')
                            emb = embedder.get_embedding(pil_img)
                            
                            cursor.execute(
                                "INSERT INTO products (product_id, name, category, price, image_path, stock) VALUES (?, ?, ?, ?, ?, ?)",
                                (prod_id, name, category, price, relative_path, stock)
                            )
                            
                            search_index.add_product(prod_id, emb)
                            new_products_found.append(name)
                        except Exception as e:
                            print(f"Auto-sync embedding error: {e}", flush=True)
                    
                    conn.commit()
                    search_index.save()
                    
                    elapsed = time.time() - start_time
                    print(f"[Sync Engine] Sync complete. Added: {added_count}, Removed: {deleted_count} in {elapsed:.1f}s.", flush=True)
                    summary_msg = f"SUCCESS_SYNC:{added_count}:{deleted_count}:{elapsed:.1f}"
                    self.finished.emit(True, summary_msg)
                else:
                    self.finished.emit(True, "NO_CHANGES")
                
                conn.close()
                
            elif self.task_type == "reset_catalog":
                import time
                import hashlib
                start_time = time.time()
                print("[Dev Tool] Starting Catalog-only Reset (Preserving Shoppers & Event History)...", flush=True)
                self.status_update.emit("Clearing products catalog and index binaries...")
                
                # Resolve paths
                from database.connection import get_connection, DATABASE_PATH
                from retrieval.search_index import INDEX_FILE_PATH, METADATA_FILE_PATH
                import os
                import sqlite3
                from PIL import Image
                from models.embedder import EmbeddingGenerator
                from retrieval.search_index import SearchIndex
                import numpy as np
                
                # 1. Clear products table in database
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM products")
                conn.commit()
                conn.close()
                print("[Dev Tool] Cleared products table. Shoppers & history preserved.", flush=True)
                
                # 2. Wipe index files
                for path in [INDEX_FILE_PATH, METADATA_FILE_PATH]:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            print(f"[Dev Tool] Deleted index file {os.path.basename(path)}.", flush=True)
                        except Exception as e:
                            print(f"[Dev Tool] Error deleting index file: {e}", flush=True)
                            
                # 3. Scan dataset folders
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                dataset_root = os.path.join(app_root, "datasets", "tanishq-jewellery-dataset")
                
                if not os.path.exists(dataset_root):
                    print(f"[Dev Tool] Dataset root not found: {dataset_root}", flush=True)
                    self.status_update.emit("⚠️ Datasets folder not found!")
                    self.finished.emit(False, f"Dataset folder not found at {dataset_root}")
                    return
                    
                categories = ["Rings", "Necklaces", "Earrings", "Bangles"]
                files_to_add = []
                
                for category in categories:
                    cat_dir = os.path.join(dataset_root, category)
                    if not os.path.exists(cat_dir):
                        continue
                    for filename in os.listdir(cat_dir):
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            full_path = os.path.join(cat_dir, filename)
                            files_to_add.append((category, filename, full_path))
                            
                print(f"[Dev Tool] Found {len(files_to_add)} products to import.", flush=True)
                
                self.status_update.emit("Instantiating CLIP deep models...")
                embedder = self.params.get("embedder")
                if embedder is None:
                    embedder = EmbeddingGenerator()
                search_index = self.params.get("search_index")
                if search_index is None:
                    search_index = SearchIndex(dimension=embedder.get_dim())
                search_index.clear()
                
                conn = get_connection()
                cursor = conn.cursor()
                
                success_count = 0
                for idx, (category, filename, full_path) in enumerate(files_to_add):
                    if getattr(self, 'is_cancelled', False):
                        print("[Dev Tool] Reset cancelled by user.", flush=True)
                        conn.commit()
                        conn.close()
                        self.finished.emit(False, "Cancelled by user")
                        return
                        
                    # Deterministic Product ID based on path hash
                    relative_path = f"visual_search_engine/datasets/tanishq-jewellery-dataset/{category}/{filename}"
                    norm_path = relative_path.replace("\\", "/").lower()
                    h = hashlib.md5(norm_path.encode('utf-8')).hexdigest()
                    prod_id = f"prod_{h[:12]}"
                    
                    name = f"Auto {category[:-1]} - {filename.split('.')[0].split('_')[0].split('-')[0].replace('_', ' ').replace('-', ' ').title()}"
                    price, stock = parse_price_stock_from_filename(filename)
                    
                    try:
                        self.status_update.emit(f"Importing {idx+1}/{len(files_to_add)}: {filename}")
                        pil_img = Image.open(full_path).convert('RGB')
                        emb = embedder.get_embedding(pil_img)
                        
                        cursor.execute(
                            "INSERT INTO products (product_id, name, category, price, image_path, stock) VALUES (?, ?, ?, ?, ?, ?)",
                            (prod_id, name, category, price, relative_path, stock)
                        )
                        search_index.add_product(prod_id, emb)
                        success_count += 1
                    except Exception as e:
                        print(f"[Dev Tool] Reset embedding error: {e}", flush=True)
                        
                conn.commit()
                conn.close()
                
                if success_count > 0:
                    search_index.save()
                    
                elapsed = time.time() - start_time
                print(f"[Dev Tool] Reset Catalog successful. Imported {success_count} products in {elapsed:.1f}s.", flush=True)
                self.finished.emit(True, f"Successfully rebuilt catalog with {success_count} products in {elapsed:.1f}s. Customer profiles and history logs were preserved!")
                
            elif self.task_type == "bootstrap":
                import time
                start_time = time.time()
                print("[Dev Tool] Starting wipe & bootstrap of the entire system...", flush=True)
                self.status_update.emit("Wiping SQLite database and index binaries...")
                
                # Resolve paths
                from database.connection import DATABASE_PATH
                from retrieval.search_index import INDEX_FILE_PATH, METADATA_FILE_PATH
                import os
                
                # 1. Wipe SQLite database file if it exists
                if os.path.exists(DATABASE_PATH):
                    try:
                        os.remove(DATABASE_PATH)
                        print("[Dev Tool] Deleted active database file database.db.", flush=True)
                    except Exception as e:
                        print(f"[Dev Tool] Error deleting database.db: {e}", flush=True)
                        
                # 2. Wipe index files
                for path in [INDEX_FILE_PATH, METADATA_FILE_PATH]:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                            print(f"[Dev Tool] Deleted index file {os.path.basename(path)}.", flush=True)
                        except Exception as e:
                            print(f"[Dev Tool] Error deleting index file: {e}", flush=True)
                
                # 3. Bootstrap data from scratch
                from utils.data_generator import bootstrap_data
                
                print("[Dev Tool] Seeding database tables, users, and user events...", flush=True)
                self.status_update.emit("Seeding table structures, users, and interactions...")
                bootstrap_data(rebuild_index=False)
                
                print("[Dev Tool] Database successfully seeded. Building vector search index...", flush=True)
                self.status_update.emit("Loading newly seeded catalog...")
                from database.connection import get_connection
                from models.embedder import EmbeddingGenerator
                from retrieval.search_index import SearchIndex
                from PIL import Image
                
                conn = get_connection()
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT product_id, image_path FROM products")
                rows = cursor.fetchall()
                conn.close()
                
                self.status_update.emit("Instantiating CLIP deep models...")
                embedder = self.params.get("embedder")
                if embedder is None:
                    embedder = EmbeddingGenerator()
                search_index = self.params.get("search_index")
                if search_index is None:
                    search_index = SearchIndex(dimension=embedder.get_dim())
                search_index.clear()
                
                self.status_update.emit(f"Catalog loaded ({len(rows)} items). Rebuilding indices...")
                success_count = 0
                app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                for idx, row in enumerate(rows):
                    if getattr(self, 'is_cancelled', False):
                        print("[Dev Tool] Operation cancelled by user.", flush=True)
                        self.finished.emit(False, "Cancelled by user")
                        return
                        
                    prod_id = row['product_id']
                    img_path = row['image_path']
                    
                    actual_img_path = img_path
                    if img_path and not os.path.isabs(img_path):
                        clean_path = img_path
                        if img_path.startswith("visual_search_engine/"):
                            clean_path = img_path[len("visual_search_engine/"):]
                        elif img_path.startswith("visual_search_engine\\"):
                            clean_path = img_path[len("visual_search_engine\\"):]
                        actual_img_path = os.path.join(app_root, clean_path)
                        
                    self.status_update.emit(f"Wipe & Seed progress: Embedding {idx+1}/{len(rows)}...")
                        
                    if not actual_img_path or not os.path.exists(actual_img_path):
                        continue
                        
                    try:
                        print(f"[Dev Tool] Rebuilding vector {idx+1}/{len(rows)}: {os.path.basename(actual_img_path)}", flush=True)
                        pil_img = Image.open(actual_img_path).convert('RGB')
                        emb = embedder.get_embedding(pil_img)
                        search_index.add_product(prod_id, emb)
                        success_count += 1
                    except Exception as e:
                        print(f"[Dev Tool] Embedding generation failed for {prod_id}: {e}", flush=True)
                        
                if success_count > 0:
                    search_index.save()
                    
                elapsed = time.time() - start_time
                print(f"[Dev Tool] Wipe & Bootstrap complete! Processed {success_count} vectors in {elapsed:.1f}s.", flush=True)
                self.finished.emit(True, f"Successfully wiped and bootstrapped system with {success_count} vectors in {elapsed:.1f}s.")
        except Exception as e:
            self.finished.emit(False, str(e))


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

    def plot_bar(self, categories, values, title, colors=None):
        if not HAS_MATPLOTLIB:
            return
        self.axes.clear()
        if colors is None:
            colors = ['#38bdf8', '#34d399', '#f43f5e', '#a855f7']
        bars = self.axes.bar(categories, values, color=colors[:len(categories)], width=0.45)
        
        # Add labels on top of each bar
        max_val = max(values) if values else 0
        for bar in bars:
            height = bar.get_height()
            self.axes.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + (max_val * 0.015 + 0.1),
                f'{int(height)}',
                ha='center',
                va='bottom',
                color='#e2e8f0',
                fontsize=9,
                fontweight='bold'
            )
            
        self.axes.set_title(title, color='#f8fafc', fontsize=11, fontweight='bold', pad=10)
        self.axes.tick_params(colors='#94a3b8', labelsize=9)
        
        # Grid
        self.axes.grid(True, color='#334155', linestyle='--', alpha=0.5)
        self.axes.spines['bottom'].set_color('#334155')
        self.axes.spines['top'].set_color('none')
        self.axes.spines['right'].set_color('none')
        self.axes.spines['left'].set_color('#334155')
        
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Main Admin tab container
        self.admin_tabs = QTabWidget(self)
        self.admin_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0f172a;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #0f172a;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
        """)
        
        # ----------------------------------------------------
        # Tab 1: Live Analytics & KPIs (Scrollable)
        # ----------------------------------------------------
        analytics_scroll = QScrollArea(self)
        analytics_scroll.setWidgetResizable(True)
        analytics_scroll.setStyleSheet("background-color: transparent; border: none;")
        
        analytics_content = QWidget()
        analytics_layout = QVBoxLayout(analytics_content)
        analytics_layout.setContentsMargins(12, 12, 12, 12)
        analytics_layout.setSpacing(12)
        
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)
        
        self.kpi_prod = self.create_kpi_card("📦 Total Products", "0")
        self.kpi_user = self.create_kpi_card("👥 Active Users", "0")
        self.kpi_event = self.create_kpi_card("🖱️ Total Events", "0")
        self.kpi_faiss = self.create_kpi_card("🔍 Index Capacity", "0")
        
        kpi_layout.addWidget(self.kpi_prod)
        kpi_layout.addWidget(self.kpi_user)
        kpi_layout.addWidget(self.kpi_event)
        kpi_layout.addWidget(self.kpi_faiss)
        analytics_layout.addLayout(kpi_layout)
        
        # Matplotlib chart container
        chart_card = QFrame(analytics_content)
        chart_card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        chart_card_layout = QVBoxLayout(chart_card)
        
        chart_ctrl_row = QHBoxLayout()
        chart_lbl = QLabel("Analytics View:", chart_card)
        chart_lbl.setStyleSheet("font-weight: bold; color: #f8fafc; font-size: 12px;")
        chart_ctrl_row.addWidget(chart_lbl)
        
        self.chart_selector = QComboBox(chart_card)
        self.chart_selector.addItems(["Shopper Event Breakdown", "Category Inventory Sizes"])
        self.chart_selector.currentTextChanged.connect(self.update_charts)
        chart_ctrl_row.addWidget(self.chart_selector)
        chart_ctrl_row.addStretch()
        chart_card_layout.addLayout(chart_ctrl_row)
        
        self.chart_canvas = MplCanvas(self, width=5, height=3.5)
        self.chart_canvas.setMinimumHeight(280)
        chart_card_layout.addWidget(self.chart_canvas)
        
        analytics_layout.addWidget(chart_card)
        analytics_scroll.setWidget(analytics_content)
        self.admin_tabs.addTab(analytics_scroll, "📊 Analytics Dashboard")
        
        # ----------------------------------------------------
        # Tab 2: Directory & Event Logs (Sub-Tabbed UI)
        # ----------------------------------------------------
        directory_tab = QWidget()
        directory_layout = QVBoxLayout(directory_tab)
        directory_layout.setContentsMargins(12, 12, 12, 12)
        directory_layout.setSpacing(10)
        
        self.registry_subtabs = QTabWidget(directory_tab)
        self.registry_subtabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #1e293b;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 6px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: #1e293b;
                color: #10b981;
                border-bottom: 2px solid #10b981;
            }
        """)
        
        # Sub-tab 1: Product list directory
        prod_widget = QWidget()
        prod_layout = QVBoxLayout(prod_widget)
        prod_layout.setContentsMargins(10, 10, 10, 10)
        
        self.table = QTableWidget(prod_widget)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Select", "ID", "Image", "Name", "Category", "Price", "Stock"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Connect double click to view details dialog
        self.table.itemDoubleClicked.connect(self.on_table_row_double_clicked)
        # Connect item changed for inline stock editing
        self.table.itemChanged.connect(self.on_table_item_changed)
        
        prod_layout.addWidget(self.table)
        
        # Horizontal action buttons row
        actions_layout = QHBoxLayout()
        
        self.delete_btn = QPushButton("❌ Delete Selected Product(s)", prod_widget)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e11d48;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #be123c;
            }
        """)
        self.delete_btn.clicked.connect(self.on_delete_products)
        actions_layout.addWidget(self.delete_btn)
        
        self.edit_stock_btn = QPushButton("✏️ Update Selected Stock", prod_widget)
        self.edit_stock_btn.setStyleSheet("""
            QPushButton {
                background-color: #0ea5e9;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        self.edit_stock_btn.clicked.connect(self.on_edit_stock_clicked)
        actions_layout.addWidget(self.edit_stock_btn)
        
        prod_layout.addLayout(actions_layout)
        
        self.registry_subtabs.addTab(prod_widget, "📦 Product Catalog Directory")
        
        # Sub-tab 2: User events trails
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        logs_layout.setSpacing(8)
        
        # Date-wise Calendar Filter Row
        filter_row = QHBoxLayout()
        
        self.date_filter_checkbox = QCheckBox("Filter by Specific Calendar Date:", logs_widget)
        self.date_filter_checkbox.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px;")
        filter_row.addWidget(self.date_filter_checkbox)
        
        self.log_date = QDateEdit(logs_widget)
        self.log_date.setCalendarPopup(True)
        self.log_date.setDate(QDate.currentDate())
        self.log_date.setStyleSheet("QDateEdit { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 4px; border-radius: 4px; }")
        filter_row.addWidget(self.log_date)
        
        self.filter_btn = QPushButton("🔍 Filter Logs", logs_widget)
        self.filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.filter_btn.clicked.connect(self.load_shopper_logs)
        filter_row.addWidget(self.filter_btn)
        
        filter_row.addStretch()
        logs_layout.addLayout(filter_row)
        
        self.logs_table = QTableWidget(logs_widget)
        self.logs_table.setColumnCount(5)
        self.logs_table.setHorizontalHeaderLabels(["User ID", "Product Name", "Action Type", "Timestamp", "Dwell Time (s)"])
        self.logs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.logs_table.setSelectionBehavior(QTableWidget.SelectRows)
        logs_layout.addWidget(self.logs_table)
        
        # Connect signals for interactive thumbnails and rows clicks
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        
        self.registry_subtabs.addTab(logs_widget, "📋 Live Activity Events Log")
        
        directory_layout.addWidget(self.registry_subtabs)
        self.admin_tabs.addTab(directory_tab, "📦 Logs & Registry")
        
        # ----------------------------------------------------
        # Tab 3: System Admin Tools (Scrollable)
        # ----------------------------------------------------
        tools_scroll = QScrollArea(self)
        tools_scroll.setWidgetResizable(True)
        tools_scroll.setStyleSheet("background-color: transparent; border: none;")
        
        tools_content = QWidget()
        tools_layout = QHBoxLayout(tools_content)
        tools_layout.setContentsMargins(12, 12, 12, 12)
        tools_layout.setSpacing(15)
        
        # Form to add product (Left)
        add_box = QFrame(tools_content)
        add_box.setFixedWidth(380)
        add_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 12px;")
        add_layout = QVBoxLayout(add_box)
        
        form_lbl = QLabel("Add New Inventory Product", add_box)
        form_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc; margin-bottom: 8px;")
        add_layout.addWidget(form_lbl)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        self.name_input = QLineEdit(add_box)
        form.addRow(QLabel("Product Name:", add_box), self.name_input)
        
        self.cat_combo = QComboBox(add_box)
        self.cat_combo.addItems(["Rings", "Necklaces", "Earrings", "Bangles"])
        form.addRow(QLabel("Category:", add_box), self.cat_combo)
        
        self.price_input = QLineEdit(add_box)
        form.addRow(QLabel("Price ($):", add_box), self.price_input)
        
        self.stock_input = QLineEdit(add_box)
        form.addRow(QLabel("Stock Level:", add_box), self.stock_input)
        
        img_row = QHBoxLayout()
        self.img_path_lbl = QLabel("No file chosen", add_box)
        self.img_path_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.browse_btn = QPushButton("Browse...", add_box)
        self.browse_btn.setObjectName("secondaryBtn")
        self.browse_btn.clicked.connect(self.on_browse_image)
        img_row.addWidget(self.img_path_lbl)
        img_row.addWidget(self.browse_btn)
        form.addRow(QLabel("Image File:", add_box), img_row)
        
        add_layout.addLayout(form)
        add_layout.addSpacing(10)
        
        self.add_btn = QPushButton("Add & Embed Product", add_box)
        self.add_btn.clicked.connect(self.on_add_product)
        add_layout.addWidget(self.add_btn)
        add_layout.addStretch()
        
        tools_layout.addWidget(add_box)
        
        # Instantiate invisible dummy controls to prevent AttributeError crashes in existing worker handlers
        self.rebuild_btn = QPushButton(self)
        self.rebuild_btn.setVisible(False)
        self.sync_btn = QPushButton(self)
        self.sync_btn.setVisible(False)
        
        self.cancel_rebuild_btn = QPushButton(self)
        self.cancel_rebuild_btn.setVisible(False)
        self.cancel_sync_btn = QPushButton(self)
        self.cancel_sync_btn.setVisible(False)
        
        self.rebuild_status_lbl = QLabel(self)
        self.rebuild_status_lbl.setVisible(False)
        self.sync_status_lbl = QLabel(self)
        self.sync_status_lbl.setVisible(False)
        
        self.last_sync_lbl = QLabel(self)
        self.last_sync_lbl.setVisible(False)
        
        # Add stretch to center the Add Product tool beautifully
        tools_layout.addStretch()
        
        tools_scroll.setWidget(tools_content)
        self.admin_tabs.addTab(tools_scroll, "⚙️ Admin Tools")
        
        # Tab 4: Customer Profiles Watch
        profile_watch_widget = QWidget(self)
        profile_watch_layout = QVBoxLayout(profile_watch_widget)
        profile_watch_layout.setContentsMargins(12, 12, 12, 12)
        profile_watch_layout.setSpacing(10)
        
        # Selector row
        sel_row = QHBoxLayout()
        sel_lbl = QLabel("Select Customer Profile to View:", profile_watch_widget)
        sel_lbl.setStyleSheet("font-weight: bold; color: #cbd5e1; font-size: 13px; border: none; background: transparent;")
        sel_row.addWidget(sel_lbl)
        
        self.cust_combo = QComboBox(profile_watch_widget)
        self.cust_combo.setFixedWidth(240)
        self.cust_combo.setStyleSheet("QComboBox { background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 5px; border-radius: 4px; }")
        self.cust_combo.currentIndexChanged.connect(self.on_cust_selection_changed)
        
        self.add_user_btn = QPushButton("➕ Add User", profile_watch_widget)
        self.add_user_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.add_user_btn.clicked.connect(self.on_add_user_clicked)
        
        self.del_user_btn = QPushButton("❌ Delete User", profile_watch_widget)
        self.del_user_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.del_user_btn.clicked.connect(self.on_delete_user_clicked)
        
        sel_row.addWidget(self.cust_combo)
        sel_row.addWidget(self.add_user_btn)
        sel_row.addWidget(self.del_user_btn)
        sel_row.addStretch()
        profile_watch_layout.addLayout(sel_row)
        
        # User profile viewer tab widget nested
        self.profile_viewer = UserProfileTab(profile_watch_widget, admin_mode=True)
        profile_watch_layout.addWidget(self.profile_viewer)
        
        self.admin_tabs.addTab(profile_watch_widget, "👤 Customer Profiles")
        
        # ----------------------------------------------------
        # Tab 5: Dev Tool Tab (Scrollable and Styled UI/UX)
        # ----------------------------------------------------
        dev_scroll = QScrollArea(self)
        dev_scroll.setWidgetResizable(True)
        dev_scroll.setStyleSheet("background-color: transparent; border: none;")
        
        dev_scroll_content = QWidget()
        dev_scroll_content.setStyleSheet("background-color: transparent;")
        dev_layout = QVBoxLayout(dev_scroll_content)
        dev_layout.setContentsMargins(15, 15, 15, 15)
        dev_layout.setSpacing(20)
        
        # Section A: Reset Catalog Only (Safe Option)
        cat_card = QFrame(dev_scroll_content)
        cat_card.setObjectName("safeDevCard")
        cat_card.setStyleSheet("""
            QFrame#safeDevCard {
                background-color: #1e293b;
                border: 2px solid #3b82f6;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        cat_card_layout = QVBoxLayout(cat_card)
        cat_card_layout.setSpacing(12)
        
        cat_title = QLabel("🔄 Reset Catalog Only (Safe Option)", cat_card)
        cat_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        
        cat_desc = QLabel(
            "Wipes all products from the database and rebuilds the vector search index from the folders present on disk.<br>"
            "🚀 <b>Shoppers, historical activity logs, event registers, and customer profiles are kept 100% intact!</b><br>"
            "Product IDs are generated deterministically so the existing recommendation records remain linked to their items.",
            cat_card
        )
        cat_desc.setWordWrap(True)
        cat_desc.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.5;")
        
        self.dev_reset_cat_btn = QPushButton("📦 Reset Catalog (Preserve Shoppers & History)", cat_card)
        self.dev_reset_cat_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 18px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.dev_reset_cat_btn.clicked.connect(self.on_dev_reset_catalog)
        
        self.dev_cancel_cat_btn = QPushButton("🛑 Cancel Catalog Reset", cat_card)
        self.dev_cancel_cat_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: #ffffff;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.dev_cancel_cat_btn.setVisible(False)
        self.dev_cancel_cat_btn.clicked.connect(self.on_cancel_dev_reset_catalog)
        
        self.dev_cat_status_lbl = QLabel("", cat_card)
        self.dev_cat_status_lbl.setStyleSheet("color: #38bdf8; font-size: 12px; font-weight: bold; margin-top: 4px;")
        
        cat_card_layout.addWidget(cat_title)
        cat_card_layout.addWidget(cat_desc)
        cat_card_layout.addWidget(self.dev_reset_cat_btn)
        cat_card_layout.addWidget(self.dev_cancel_cat_btn)
        cat_card_layout.addWidget(self.dev_cat_status_lbl)
        
        dev_layout.addWidget(cat_card)
        
        # Section B: Full System Wipe (High Risk Option)
        dev_card = QFrame(dev_scroll_content)
        dev_card.setObjectName("riskDevCard")
        dev_card.setStyleSheet("""
            QFrame#riskDevCard {
                background-color: #1e293b;
                border: 2px solid #ef4444;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        dev_card_layout = QVBoxLayout(dev_card)
        dev_card_layout.setSpacing(12)
        
        dev_title = QLabel("⚠️ System Reset & Dev Bootstrap (High Risk Option)", dev_card)
        dev_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f87171;")
        
        dev_desc = QLabel(
            "Deletes the <code>database.db</code> SQLite file, drops all tables, and deletes all vector indexing binaries.<br>"
            "💥 <b>This will completely wipe all customer profiles, registered accounts, wishlist/purchase records, and logs!</b><br>"
            "The system is re-initialized with fresh sample buyers, dummy event history, and vector embeddings generated from scratch.",
            dev_card
        )
        dev_desc.setWordWrap(True)
        dev_desc.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.5;")
        
        self.dev_wipe_btn = QPushButton("💥 Wipe & Bootstrap Database from Scratch", dev_card)
        self.dev_wipe_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 18px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        self.dev_wipe_btn.clicked.connect(self.on_dev_wipe_database)
        
        self.dev_cancel_btn = QPushButton("🛑 Cancel Bootstrap Action", dev_card)
        self.dev_cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                color: #ffffff;
                font-weight: bold;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.dev_cancel_btn.setVisible(False)
        self.dev_cancel_btn.clicked.connect(self.on_cancel_dev_wipe)
        
        self.dev_status_lbl = QLabel("", dev_card)
        self.dev_status_lbl.setStyleSheet("color: #f87171; font-size: 12px; font-weight: bold; margin-top: 4px;")
        
        dev_card_layout.addWidget(dev_title)
        dev_card_layout.addWidget(dev_desc)
        dev_card_layout.addWidget(self.dev_wipe_btn)
        dev_card_layout.addWidget(self.dev_cancel_btn)
        dev_card_layout.addWidget(self.dev_status_lbl)
        
        dev_layout.addWidget(dev_card)
        dev_layout.addStretch()
        
        dev_scroll.setWidget(dev_scroll_content)
        self.admin_tabs.addTab(dev_scroll, "🔧 Dev Tool")
        
        main_layout.addWidget(self.admin_tabs)
        
        # Setup sync metadata
        self.metadata_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sync_metadata.json")
        self.load_sync_metadata()
        
        self.refresh_view()

    def create_kpi_card(self, title, val):
        card = QFrame(self)
        card.setMinimumHeight(65)
        card.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        
        title_lbl = QLabel(title, card)
        title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold; background: transparent; padding: 0px;")
        title_lbl.setAlignment(Qt.AlignCenter)
        
        val_lbl = QLabel(val, card)
        val_lbl.setStyleSheet("color: #38bdf8; font-size: 18px; font-weight: bold; background: transparent; padding: 0px;")
        val_lbl.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)
        
        card.val_lbl = val_lbl
        return card

    def refresh_view(self):
        self.load_products_table()
        self.load_shopper_logs()
        self.update_stats()
        self.update_charts()
        self.load_customers_list()

    def load_customers_list(self):
        # Block signals to prevent triggering events during load
        self.cust_combo.blockSignals(True)
        # Store currently selected user_id if any to restore selection
        selected_user_id = None
        if self.cust_combo.currentIndex() >= 0:
            selected_user_id = self.cust_combo.currentData()
            
        self.cust_combo.clear()
        
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, profile_type FROM users ORDER BY name ASC")
        users = cursor.fetchall()
        conn.close()
        
        restore_idx = 0
        for idx, u in enumerate(users):
            self.cust_combo.addItem(f"{u['name']} ({u['profile_type']})", u['user_id'])
            if selected_user_id and u['user_id'] == selected_user_id:
                restore_idx = idx
                
        self.cust_combo.blockSignals(False)
        
        if self.cust_combo.count() > 0:
            self.cust_combo.setCurrentIndex(restore_idx)
            self.on_cust_selection_changed(restore_idx)

    def on_cust_selection_changed(self, idx):
        if idx >= 0:
            user_id = self.cust_combo.itemData(idx)
            self.profile_viewer.set_user(user_id)

    def on_table_item_changed(self, item):
        # Ignore changes while loading the table contents programmatically
        if getattr(self, 'loading_table', False):
            return
        row = item.row()
        col = item.column()
        if col == 6: # Stock column
            prod_id = self.table.item(row, 1).text() # ID is in Column 1
            new_stock_str = item.text().strip()
            try:
                new_stock = int(new_stock_str)
                if new_stock < 0:
                    raise ValueError("Stock cannot be negative")
                
                # Save to database
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE products SET stock = ? WHERE product_id = ?", (new_stock, prod_id))
                conn.commit()
                conn.close()
                
                # Update KPI stats & logs
                self.update_stats()
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", "Stock must be a non-negative integer!")
                # Reload table to revert invalid change
                self.load_products_table()

    def on_edit_stock_clicked(self):
        checked_rows = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                checked_rows.append(r)
                
        # Fall back to selected rows if no checkbox is checked
        if not checked_rows:
            selected_ranges = self.table.selectedRanges()
            for r in selected_ranges:
                for i in range(r.topRow(), r.bottomRow() + 1):
                    if i not in checked_rows:
                        checked_rows.append(i)
                        
        if not checked_rows:
            QMessageBox.warning(self, "Selection Error", "No products selected! Please check the boxes or select a row in the table.")
            return
            
        # Get the first selected product details
        first_row = checked_rows[0]
        prod_id = self.table.item(first_row, 1).text()
        current_name = self.table.item(first_row, 3).text()
        current_stock_str = self.table.item(first_row, 6).text()
        
        try:
            current_stock = int(current_stock_str)
        except ValueError:
            current_stock = 0
            
        new_stock, ok = QInputDialog.getInt(
            self, "Update Stock Level",
            f"Enter new stock level for '{current_name}' (ID: {prod_id}):",
            current_stock, 0, 100000, 1
        )
        if ok:
            try:
                # Save to database
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE products SET stock = ? WHERE product_id = ?", (new_stock, prod_id))
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Success", f"Stock level for '{current_name}' successfully updated to {new_stock} units.")
                self.refresh_view()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update stock: {e}")

    def update_stats(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM products")
        n_prod = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        n_user = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_events JOIN products ON user_events.product_id = products.product_id")
        n_event = cursor.fetchone()[0]
        
        conn.close()
        
        self.kpi_prod.val_lbl.setText(str(n_prod))
        self.kpi_user.val_lbl.setText(str(n_user))
        self.kpi_event.val_lbl.setText(str(n_event))
        self.kpi_faiss.val_lbl.setText(f"{n_prod} vectors")

    def update_charts(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        chart_mode = self.chart_selector.currentText()
        
        if chart_mode == "Shopper Event Breakdown":
            cursor.execute("""
                SELECT event_type, COUNT(*) 
                FROM user_events 
                JOIN products ON user_events.product_id = products.product_id 
                GROUP BY event_type
            """)
            rows = cursor.fetchall()
            conn.close()
            
            categories = [r[0].capitalize() for r in rows]
            counts = [r[1] for r in rows]
            if not categories:
                categories = ["View", "Click", "Wishlist", "Purchase"]
                counts = [0, 0, 0, 0]
                
            self.chart_canvas.plot_bar(categories, counts, "User Actions Volume Breakdown", colors=['#38bdf8', '#34d399', '#f43f5e', '#a855f7'])
        else:
            cursor.execute("SELECT category, COUNT(*) FROM products GROUP BY category")
            rows = cursor.fetchall()
            conn.close()
            
            categories = [r[0] for r in rows]
            counts = [r[1] for r in rows]
            if not categories:
                categories = ["Rings", "Necklaces", "Earrings", "Bangles"]
                counts = [0, 0, 0, 0]
                
            self.chart_canvas.plot_bar(categories, counts, "Catalog Sizes by Category", colors=['#fb7185', '#60a5fa', '#34d399', '#facc15'])

    def load_products_table(self):
        self.loading_table = True
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, name, category, price, stock, image_path FROM products ORDER BY rowid DESC")
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(len(rows))
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for row_idx, row in enumerate(rows):
            # Column 0: Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, chk_item)
            
            # Column 1: ID
            id_item = QTableWidgetItem(row['product_id'])
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, id_item)
            
            # Column 2: Image Thumbnail
            img_lbl = QLabel()
            img_lbl.setFixedSize(40, 40)
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setStyleSheet("border: 1px solid #334155; border-radius: 4px; background-color: #0f172a;")
            
            img_path = row['image_path']
            actual_img_path = img_path
            if img_path and not os.path.isabs(img_path):
                clean_path = img_path
                if img_path.startswith("visual_search_engine/"):
                    clean_path = img_path[len("visual_search_engine/"):]
                elif img_path.startswith("visual_search_engine\\"):
                    clean_path = img_path[len("visual_search_engine\\"):]
                actual_img_path = os.path.join(app_root, clean_path)
                
            if actual_img_path and os.path.exists(actual_img_path):
                pix = QPixmap(actual_img_path)
                img_lbl.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("💍")
                img_lbl.setStyleSheet("color: #64748b; font-size: 14px; border: none;")
                
            self.table.setCellWidget(row_idx, 2, img_lbl)
            
            # Columns 3 to 6: Name, Category, Price, Stock
            name_item = QTableWidgetItem(row['name'])
            self.table.setItem(row_idx, 3, name_item)
            
            cat_item = QTableWidgetItem(row['category'])
            self.table.setItem(row_idx, 4, cat_item)
            
            price_item = QTableWidgetItem(f"${row['price']:.2f}")
            price_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 5, price_item)
            
            stock_item = QTableWidgetItem(str(row['stock']))
            stock_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, stock_item)
            
        self.table.setIconSize(QSize(40, 40))
        for i in range(len(rows)):
            self.table.setRowHeight(i, 46)
        self.loading_table = False

    def on_table_row_double_clicked(self, item):
        row = item.row()
        prod_id = self.table.item(row, 1).text() # ID is in Column 1
        
        from gui.components import ProductDetailsDialog
        dialog = ProductDetailsDialog(prod_id, parent=self)
        dialog.exec()

    def on_table_cell_clicked(self, row, col):
        # Column 2 is the Image thumbnail column
        if col == 2:
            prod_id = self.table.item(row, 1).text() # ID is in Column 1
            from gui.components import ProductDetailsDialog
            dialog = ProductDetailsDialog(prod_id, parent=self)
            dialog.exec()

    def load_shopper_logs(self):
        query = """
            SELECT user_id, name, event_type, timestamp, dwell_time 
            FROM user_events 
            JOIN products ON user_events.product_id = products.product_id
        """
        params = []
        
        # Filter by specific calendar date if checked (Optimized using index-friendly BETWEEN)
        if self.date_filter_checkbox.isChecked():
            chosen_date = self.log_date.date().toString("yyyy-MM-dd")
            query += " WHERE timestamp BETWEEN ? AND ?"
            params.append(f"{chosen_date} 00:00:00")
            params.append(f"{chosen_date} 23:59:59")
            
        query += " ORDER BY timestamp DESC LIMIT 100"
        
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) == 0:
            self.logs_table.setRowCount(1)
            for c in range(5):
                self.logs_table.setItem(0, c, QTableWidgetItem(""))
            placeholder = QTableWidgetItem("⚠️ No data here. Please choose another date in the filter above.")
            placeholder.setTextAlignment(Qt.AlignCenter)
            placeholder.setFlags(Qt.ItemIsEnabled)
            self.logs_table.setItem(0, 2, placeholder)
            return

        self.logs_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            self.logs_table.setItem(row_idx, 0, QTableWidgetItem(row['user_id']))
            self.logs_table.setItem(row_idx, 1, QTableWidgetItem(row['name']))
            self.logs_table.setItem(row_idx, 2, QTableWidgetItem(row['event_type'].capitalize()))
            self.logs_table.setItem(row_idx, 3, QTableWidgetItem(row['timestamp']))
            self.logs_table.setItem(row_idx, 4, QTableWidgetItem(str(row['dwell_time'])))
            
            for col in [0, 2, 3, 4]:
                self.logs_table.item(row_idx, col).setTextAlignment(Qt.AlignCenter)

    def on_add_user_clicked(self):
        from PySide6.QtWidgets import QInputDialog
        import uuid
        name, ok = QInputDialog.getText(self, "Add User Profile", "Enter shopper name:")
        if not ok or not name.strip():
            return
            
        tier, ok = QInputDialog.getItem(self, "Add User Profile", "Select Tier Profile:", ["Regular", "Gold", "Diamond"], 0, False)
        if not ok:
            return
            
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (user_id, name, profile_type) VALUES (?, ?, ?)", (user_id, name.strip(), tier))
            conn.commit()
            QMessageBox.information(self, "Success", f"User profile '{name}' added successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add user: {e}")
        finally:
            conn.close()
            
        self.load_customers_list()

    def on_delete_user_clicked(self):
        idx = self.cust_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Warning", "No customer selected!")
            return
            
        user_id = self.cust_combo.itemData(idx)
        user_name = self.cust_combo.currentText().split(" (")[0]
        
        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            f"Are you sure you want to delete user '{user_name}'?\nThis will completely delete all their event history and logs!",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
            
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM user_events WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            conn.commit()
            QMessageBox.information(self, "Success", f"User profile '{user_name}' and all logs deleted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete user: {e}")
        finally:
            conn.close()
            
        self.load_customers_list()

    def on_browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Product Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.selected_img_path = file_path
            self.img_path_lbl.setText(os.path.basename(file_path))

    def on_add_product(self):
        # Block if any worker is currently running
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "An embedding or database synchronization process is currently in progress. Please wait until it completes.")
            return

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
            
        # Capture old count before starting thread
        self.search_index.load()
        self.old_vector_count = len(self.search_index.product_ids)
        self.new_product_name = name
        
        # Disable button and show progress indicator
        self.add_btn.setEnabled(False)
        self.add_btn.setText("Adding & Embedding Product...")
        
        # Start background worker thread
        self.add_worker = DbWorker("add", {
            "name": name,
            "category": category,
            "price": price,
            "stock": stock,
            "selected_img_path": self.selected_img_path,
            "embedder": self.embedder,
            "search_index": self.search_index
        })
        self.add_worker.finished.connect(self.on_add_finished)
        self.add_worker.start()

    def on_add_finished(self, success, msg):
        self.add_btn.setEnabled(True)
        self.add_btn.setText("Add & Embed Product")
        if success:
            self.search_index.load()
            new_count = len(self.search_index.product_ids)
            
            notification_text = (
                f"✨ Product Added & Embedded successfully!\n\n"
                f"• Previous Index Size: {self.old_vector_count} vectors\n"
                f"• Current Index Size: {new_count} vectors\n"
                f"• Added: {self.new_product_name} (1 new vector index committed)\n\n"
                f"The product is now active in visual search and recommender layers."
            )
            QMessageBox.information(self, "Product Insertion Successful", notification_text)
            
            # Clear inputs
            self.name_input.clear()
            self.price_input.clear()
            self.stock_input.clear()
            self.img_path_lbl.setText("No file chosen")
            self.selected_img_path = None
            self.refresh_view()
        else:
            QMessageBox.critical(self, "Product Insertion Failed", f"Failed to add product: {msg}")

    def auto_scan_folder(self):
        # Prevent auto-scan if any indexing or database worker is currently running
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()):
            return
            
        self.scan_worker = DbWorker("auto_sync", {
            "embedder": self.embedder,
            "search_index": self.search_index
        })
        self.scan_worker.finished.connect(self.on_auto_sync_finished)
        self.scan_worker.start()
        
    def on_auto_sync_finished(self, success, msg):
        if hasattr(self, 'sync_status_lbl'):
            self.sync_status_lbl.clear()
        if not success:
            print(f"Auto-sync background task failed: {msg}")
            return
            
        if msg == "NO_CHANGES":
            return
            
        if msg.startswith("SUCCESS_SYNC:"):
            parts = msg.split(":")
            added = int(parts[1])
            deleted = int(parts[2])
            elapsed = float(parts[3])
            
            self.search_index.load()
            self.refresh_view()
            
            notification_text = (
                f"🔄 Auto-Detector Database Sync completed in {elapsed:.1f}s!\n\n"
                f"• Added Products: {added} new items indexed\n"
                f"• Removed Products: {deleted} missing items purged\n"
                f"• Total Active Vectors: {len(self.search_index.product_ids)}\n\n"
                f"Folder updates successfully synchronized."
            )
            QMessageBox.information(self, "Auto-Sync Successful", notification_text)

    def on_rebuild_index(self):
        # Block if any worker is currently running
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "An embedding or database synchronization process is currently in progress. Please wait until it completes.")
            return

        self.rebuild_btn.setEnabled(False)
        self.cancel_rebuild_btn.setVisible(True)
        self.cancel_rebuild_btn.setEnabled(True)
        
        # Capture old count & estimate time
        self.search_index.load()
        self.old_vector_count = len(self.search_index.product_ids)
        est_seconds = max(1.0, round(self.old_vector_count * 0.06, 1))
        
        self.rebuild_btn.setText(f"Syncing Vector DB (Est. {est_seconds}s remaining)...")
        
        self.rebuild_worker = DbWorker("rebuild", {"embedder": self.embedder, "search_index": self.search_index})
        self.rebuild_worker.status_update.connect(self.rebuild_status_lbl.setText)
        self.rebuild_worker.finished.connect(self.on_rebuild_finished)
        self.rebuild_worker.start()

    def on_cancel_rebuild(self):
        if hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning():
            self.rebuild_worker.cancel()
            self.cancel_rebuild_btn.setEnabled(False)
            self.rebuild_btn.setText("Cancelling Rebuild...")

    def on_rebuild_finished(self, success, msg):
        self.rebuild_btn.setEnabled(True)
        self.rebuild_btn.setText("🔄 Rebuild FAISS Vector Index")
        self.cancel_rebuild_btn.setVisible(False)
        self.rebuild_status_lbl.clear()
        
        if success:
            self.search_index.load()
            new_count = len(self.search_index.product_ids)
            
            notification_text = (
                f"🎉 FAISS Vector Database sync rebuild successful!\n\n"
                f"• Previous Index Size: {self.old_vector_count} vectors\n"
                f"• Current Index Size: {new_count} vectors\n\n"
                f"All products are active in the AI recommendation and search engine."
            )
            QMessageBox.information(self, "Vector DB Sync Successful", notification_text)
            self.refresh_view()
        else:
            if msg == "Cancelled by user":
                QMessageBox.information(self, "Rebuild Cancelled", "Vector index rebuilding was cancelled by the user.")
            else:
                QMessageBox.critical(self, "Vector DB Sync Failed", f"Failed to rebuild index: {msg}")

    def on_trigger_sync(self):
        # Prevent parallel scans/rebuilds
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "An embedding or database synchronization process is currently in progress. Please wait until it completes.")
            return
            
        self.sync_btn.setEnabled(False)
        self.sync_btn.setText("Scanning dataset folders...")
        self.cancel_sync_btn.setVisible(True)
        self.cancel_sync_btn.setEnabled(True)
        
        self.scan_worker = DbWorker("auto_sync", {
            "embedder": self.embedder,
            "search_index": self.search_index
        })
        self.scan_worker.status_update.connect(self.sync_status_lbl.setText)
        self.scan_worker.finished.connect(self.on_auto_sync_finished)
        self.scan_worker.start()

    def on_cancel_sync(self):
        if hasattr(self, 'scan_worker') and self.scan_worker.isRunning():
            self.scan_worker.cancel()
            self.cancel_sync_btn.setEnabled(False)
            self.sync_btn.setText("Cancelling Sync...")

    def load_sync_metadata(self):
        self.last_sync_time = "Never"
        if os.path.exists(self.metadata_path):
            try:
                import json
                with open(self.metadata_path, 'r') as f:
                    data = json.load(f)
                    self.last_sync_time = data.get("last_sync", "Never")
            except Exception as e:
                print(f"Error loading sync metadata: {e}")
        if hasattr(self, 'last_sync_lbl'):
            self.last_sync_lbl.setText(f"Last Sync: {self.last_sync_time}")
            
    def save_sync_metadata(self, timestamp):
        try:
            import json
            with open(self.metadata_path, 'w') as f:
                json.dump({"last_sync": timestamp}, f)
            self.last_sync_time = timestamp
            self.last_sync_lbl.setText(f"Last Sync: {self.last_sync_time}")
        except Exception as e:
            print(f"Error saving sync metadata: {e}")

    def on_delete_products(self):
        # Block if any worker is currently running
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "An embedding or database synchronization process is currently in progress. Please wait until it completes.")
            return

        checked_rows = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                checked_rows.append(r)
                
        # Fall back to selected rows if no checkbox is checked
        if not checked_rows:
            selected_ranges = self.table.selectedRanges()
            for r in selected_ranges:
                for i in range(r.topRow(), r.bottomRow() + 1):
                    if i not in checked_rows:
                        checked_rows.append(i)
                        
        if not checked_rows:
            QMessageBox.warning(self, "Selection Error", "No products selected! Please check the boxes in the first column or select rows to delete.")
            return
            
        products_to_delete = []
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        for row in checked_rows:
            prod_id = self.table.item(row, 1).text() # ID is in Column 1
            cursor.execute("SELECT name, image_path FROM products WHERE product_id = ?", (prod_id,))
            res = cursor.fetchone()
            if res:
                products_to_delete.append((prod_id, res['name'], res['image_path']))
        conn.close()
        
        if not products_to_delete:
            return
            
        # Confirmation Dialog
        confirm_dialog = QDialog(self)
        confirm_dialog.setWindowTitle("Confirm Product Deletion")
        confirm_dialog.resize(450, 350)
        confirm_dialog.setStyleSheet("background-color: #0f172a;")
        
        dialog_layout = QVBoxLayout(confirm_dialog)
        dialog_layout.setContentsMargins(15, 15, 15, 15)
        
        warning_lbl = QLabel(f"⚠️ Are you sure you want to delete {len(products_to_delete)} product(s)?", confirm_dialog)
        warning_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #e11d48; border: none;")
        dialog_layout.addWidget(warning_lbl)
        
        if len(products_to_delete) == 1:
            prod_id, name, img_path = products_to_delete[0]
            info_lbl = QLabel(f"Product Name: {name}\nID: {prod_id}", confirm_dialog)
            info_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; border: none; margin-bottom: 5px;")
            dialog_layout.addWidget(info_lbl)
            
            img_lbl = QLabel(confirm_dialog)
            img_lbl.setFixedSize(160, 130)
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setStyleSheet("border: 1px solid #334155; border-radius: 6px; background-color: #1e293b;")
            
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            actual_img_path = img_path
            if img_path and not os.path.isabs(img_path):
                clean_path = img_path
                if img_path.startswith("visual_search_engine/"):
                    clean_path = img_path[len("visual_search_engine/"):]
                elif img_path.startswith("visual_search_engine\\"):
                    clean_path = img_path[len("visual_search_engine\\"):]
                actual_img_path = os.path.join(app_root, clean_path)
                
            if actual_img_path and os.path.exists(actual_img_path):
                pix = QPixmap(actual_img_path)
                img_lbl.setPixmap(pix.scaled(160, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("💍 No Image Available")
                img_lbl.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
            dialog_layout.addWidget(img_lbl)
        else:
            list_lbl = QLabel("Products selected for removal:\n" + "\n".join([f"• {p[1]} ({p[0]})" for p in products_to_delete[:6]]) + ("\n..." if len(products_to_delete) > 6 else ""), confirm_dialog)
            list_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; border: none; line-height: 1.4;")
            dialog_layout.addWidget(list_lbl)
            
        dialog_layout.addStretch()
        
        # Actions
        btn_row = QHBoxLayout()
        yes_btn = QPushButton("Yes, Delete All", confirm_dialog)
        yes_btn.setStyleSheet("background-color: #e11d48; color: white; padding: 7px 15px; font-weight: bold; border-radius: 4px;")
        no_btn = QPushButton("Cancel", confirm_dialog)
        no_btn.setObjectName("secondaryBtn")
        
        btn_row.addWidget(no_btn)
        btn_row.addWidget(yes_btn)
        dialog_layout.addLayout(btn_row)
        
        no_btn.clicked.connect(confirm_dialog.reject)
        
        confirmed = [False]
        def on_confirm():
            confirmed[0] = True
            confirm_dialog.accept()
        yes_btn.clicked.connect(on_confirm)
        
        confirm_dialog.exec()
        
        if not confirmed[0]:
            return
            
        # Capture old count before starting thread
        self.search_index.load()
        self.old_vector_count = len(self.search_index.product_ids)
        self.delete_targets_count = len(products_to_delete)
        
        # Responsive Button Feedback
        self.delete_btn.setEnabled(False)
        self.delete_btn.setText("❌ Deleting products & updating search index...")
        
        # Start background worker thread
        self.delete_worker = DbWorker("delete", {"products": products_to_delete, "search_index": self.search_index})
        self.delete_worker.finished.connect(self.on_delete_finished)
        self.delete_worker.start()

    def on_delete_finished(self, success, msg):
        self.delete_btn.setEnabled(True)
        self.delete_btn.setText("❌ Delete Selected Product(s)")
        if success:
            self.search_index.load()
            new_count = len(self.search_index.product_ids)
            
            notification_text = (
                f"🗑️ Product Deletion & Index Rebuild completed!\n\n"
                f"• Previous Index Size: {self.old_vector_count} vectors\n"
                f"• Current Index Size: {new_count} vectors\n"
                f"• Deleted Products: {self.delete_targets_count} items removed\n\n"
                f"Catalog updates reflected across all search and recommendation layers."
            )
            QMessageBox.information(self, "Product Deletion Successful", notification_text)
            self.refresh_view()
        else:
            QMessageBox.critical(self, "Product Deletion Failed", f"Failed to delete product(s): {msg}")

    def on_dev_wipe_database(self):
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()) or \
           (hasattr(self, 'bootstrap_worker') and self.bootstrap_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "An embedding or database synchronization process is currently in progress. Please wait until it completes.")
            return
            
        reply = QMessageBox.question(
            self, "Confirm System Reset",
            "Are you absolutely sure you want to delete the entire database and rebuild all search indices from scratch?\n\nThis will clear all current customer logs and custom products.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self.dev_wipe_btn.setEnabled(False)
        self.dev_wipe_btn.setText("💥 Wiping and bootstrapping database...")
        self.dev_cancel_btn.setVisible(True)
        self.dev_cancel_btn.setEnabled(True)
        
        self.bootstrap_worker = DbWorker("bootstrap", {
            "embedder": self.embedder,
            "search_index": self.search_index
        })
        self.bootstrap_worker.status_update.connect(self.dev_status_lbl.setText)
        self.bootstrap_worker.finished.connect(self.on_dev_wipe_finished)
        self.bootstrap_worker.start()
        
    def on_cancel_dev_wipe(self):
        if hasattr(self, 'bootstrap_worker') and self.bootstrap_worker.isRunning():
            self.bootstrap_worker.cancel()
            self.dev_cancel_btn.setEnabled(False)
            self.dev_wipe_btn.setText("Cancelling Bootstrap...")
            
    def on_dev_wipe_finished(self, success, msg):
        self.dev_wipe_btn.setEnabled(True)
        self.dev_wipe_btn.setText("💥 Wipe & Bootstrap Database from Scratch")
        self.dev_cancel_btn.setVisible(False)
        self.dev_status_lbl.clear()
        
        if success:
            self.search_index.load()
            self.refresh_view()
            self.load_customers_list()
            QMessageBox.information(self, "Reset Successful", f"💥 System successfully reset!\n\n{msg}")
        else:
            if msg == "Cancelled by user":
                QMessageBox.information(self, "Action Cancelled", "Wipe and bootstrap operation was cancelled by the user.")
            else:
                QMessageBox.critical(self, "Reset Failed", f"Failed to reset system: {msg}")

    def on_dev_reset_catalog(self):
        if (hasattr(self, 'rebuild_worker') and self.rebuild_worker.isRunning()) or \
           (hasattr(self, 'delete_worker') and self.delete_worker.isRunning()) or \
           (hasattr(self, 'add_worker') and self.add_worker.isRunning()) or \
           (hasattr(self, 'scan_worker') and self.scan_worker.isRunning()) or \
           (hasattr(self, 'bootstrap_worker') and self.bootstrap_worker.isRunning()) or \
           (hasattr(self, 'catalog_reset_worker') and self.catalog_reset_worker.isRunning()):
            QMessageBox.warning(self, "Operations Locked", "A database sync or index rebuilding process is currently in progress.")
            return
            
        reply = QMessageBox.question(
            self, "Confirm Catalog Reset",
            "Are you sure you want to clear all products and reload them from the datasets folder?\n\nShoppers, purchase logs, and profiles will be preserved.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return
            
        self.dev_reset_cat_btn.setEnabled(False)
        self.dev_reset_cat_btn.setText("Resetting catalog and index...")
        self.dev_cancel_cat_btn.setVisible(True)
        self.dev_cancel_cat_btn.setEnabled(True)
        
        self.catalog_reset_worker = DbWorker("reset_catalog", {
            "embedder": self.embedder,
            "search_index": self.search_index
        })
        self.catalog_reset_worker.status_update.connect(self.dev_cat_status_lbl.setText)
        self.catalog_reset_worker.finished.connect(self.on_dev_reset_catalog_finished)
        self.catalog_reset_worker.start()
        
    def on_cancel_dev_reset_catalog(self):
        if hasattr(self, 'catalog_reset_worker') and self.catalog_reset_worker.isRunning():
            self.catalog_reset_worker.cancel()
            self.dev_cancel_cat_btn.setEnabled(False)
            self.dev_reset_cat_btn.setText("Cancelling Catalog Reset...")
            
    def on_dev_reset_catalog_finished(self, success, msg):
        self.dev_reset_cat_btn.setEnabled(True)
        self.dev_reset_cat_btn.setText("📦 Reset Catalog (Preserve Shoppers & History)")
        self.dev_cancel_cat_btn.setVisible(False)
        self.dev_cat_status_lbl.clear()
        
        if success:
            self.search_index.load()
            self.refresh_view()
            QMessageBox.information(self, "Catalog Reset Successful", msg)
        else:
            if msg == "Cancelled by user":
                QMessageBox.information(self, "Action Cancelled", "Catalog reset operation was cancelled by the user.")
            else:
                QMessageBox.critical(self, "Reset Failed", f"Failed to reset catalog: {msg}")
