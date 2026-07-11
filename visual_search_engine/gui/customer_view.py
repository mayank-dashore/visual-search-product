from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QScrollArea, QGridLayout, QLineEdit,
                             QPushButton, QSplitter, QFrame)
from PySide6.QtCore import Qt, Slot
from gui.components import DragDropUploadWidget, ProductCard
from database.connection import get_connection
from services.tracking import track_event, get_user_events
from models.embedder import EmbeddingGenerator
from retrieval.search_index import SearchIndex
from models.recommender import HybridRecommender
from PIL import Image
import os

class CustomerViewTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user_id = 'user_1'
        self.search_image_path = None
        self.visual_similarities = []
        
        # Load models
        self.embedder = EmbeddingGenerator()
        self.search_index = SearchIndex(dimension=self.embedder.get_dim())
        self.search_index.load()
        
        self.recommender = HybridRecommender()
        self.recommender.fit()
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Splitter to divide left controls/search and right product listings
        splitter = QSplitter(Qt.Horizontal, self)
        
        # --- Left Panel (User context, Drag-and-Drop search, status) ---
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # Active profile card display
        profile_card = QFrame(self)
        profile_card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 10px;")
        profile_layout = QVBoxLayout(profile_card)
        
        profile_title = QLabel("CURRENT CUSTOMER:", profile_card)
        profile_title.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 11px;")
        profile_layout.addWidget(profile_title)
        
        self.user_profile_lbl = QLabel("Loading profile...", profile_card)
        self.user_profile_lbl.setStyleSheet("font-weight: bold; color: #f8fafc; font-size: 13px;")
        profile_layout.addWidget(self.user_profile_lbl)
        
        left_layout.addWidget(profile_card)
        
        left_layout.addSpacing(15)
        
        # Visual search drop area
        vis_search_lbl = QLabel("Visual Search Upload:", self)
        vis_search_lbl.setStyleSheet("font-weight: bold; color: #94a3b8;")
        left_layout.addWidget(vis_search_lbl)
        
        self.upload_widget = DragDropUploadWidget(self)
        self.upload_widget.imageSelected.connect(self.on_image_selected)
        left_layout.addWidget(self.upload_widget)
        
        # Text Search
        left_layout.addSpacing(15)
        text_search_lbl = QLabel("Search Jewelry by Name/Category:", self)
        text_search_lbl.setStyleSheet("font-weight: bold; color: #94a3b8;")
        left_layout.addWidget(text_search_lbl)
        
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("e.g. Ring, Gold, Necklace...")
        self.search_input.textChanged.connect(self.on_text_search_changed)
        left_layout.addWidget(self.search_input)
        
        # Clear Search button
        self.clear_btn = QPushButton("Clear Search", self)
        self.clear_btn.setObjectName("secondaryBtn")
        self.clear_btn.clicked.connect(self.clear_search)
        left_layout.addWidget(self.clear_btn)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        # --- Right Panel (Product grids) ---
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        
        # Scroll area for product grids
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("background-color: transparent; border: none;")
        
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(25)
        
        # Visually Similar Grid Section
        self.similar_lbl = QLabel("Visually Similar Products", self)
        self.similar_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        self.similar_grid = QGridLayout()
        self.scroll_layout.addWidget(self.similar_lbl)
        self.scroll_layout.addLayout(self.similar_grid)
        self.similar_lbl.hide() # Hidden initially until image upload
        
        # Personalized Recommendations Section
        self.recs_lbl = QLabel("Recommended For You", self)
        self.recs_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        self.recs_grid = QGridLayout()
        self.scroll_layout.addWidget(self.recs_lbl)
        self.scroll_layout.addLayout(self.recs_grid)
        
        # Recently Viewed Section
        self.recent_lbl = QLabel("Recently Viewed", self)
        self.recent_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #94a3b8;")
        self.recent_grid = QGridLayout()
        self.scroll_layout.addWidget(self.recent_lbl)
        self.scroll_layout.addLayout(self.recent_grid)
        
        scroll_area.setWidget(scroll_content)
        right_layout.addWidget(scroll_area)
        splitter.addWidget(right_widget)
        
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)

    def set_user(self, user_id):
        self.current_user_id = user_id
        
        # Load user name details to display on left panel
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, profile_type FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.user_profile_lbl.setText(f"👤 {row['name']}\nTier: {row['profile_type']}")
            
        self.update_recommendations()
        self.update_recently_viewed()

    def on_image_selected(self, filepath):
        self.search_image_path = filepath
        
        # Process and generate embedding
        try:
            pil_img = Image.open(filepath).convert('RGB')
            query_embedding = self.embedder.get_embedding(pil_img)
            
            # Retrieve via FAISS (top 3 matches)
            self.visual_similarities = self.search_index.search(query_embedding, k=3)
            
            # Display visually similar products
            self.similar_lbl.show()
            self.clear_layout(self.similar_grid)
            
            conn = get_connection()
            cursor = conn.cursor()
            
            for idx, (prod_id, score) in enumerate(self.visual_similarities):
                cursor.execute("SELECT * FROM products WHERE product_id = ?", (prod_id,))
                prod = cursor.fetchone()
                if prod:
                    card = ProductCard(dict(prod), score=score, parent=self)
                    card.viewed.connect(self.on_product_viewed)
                    card.wishlisted.connect(self.on_product_wishlisted)
                    card.purchased.connect(self.on_product_purchased)
                    
                    row = idx // 3
                    col = idx % 3
                    self.similar_grid.addWidget(card, row, col)
            conn.close()
            
            # Trigger recommendations updates with visual similarity weights
            self.update_recommendations()
        except Exception as e:
            print(f"Error in visual search: {e}")

    def on_text_search_changed(self, text):
        if not text:
            # Revert to normal recommendation updates
            self.update_recommendations()
            return
            
        # Basic text filter query
        conn = get_connection()
        cursor = conn.cursor()
        query = f"%{text}%"
        cursor.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? LIMIT 6", (query, query))
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Temporarily repurpose the recommendation grid to show text search results
        self.recs_lbl.setText(f"Search Results for '{text}'")
        self.clear_layout(self.recs_grid)
        
        for idx, prod in enumerate(products):
            card = ProductCard(prod, parent=self)
            card.viewed.connect(self.on_product_viewed)
            card.wishlisted.connect(self.on_product_wishlisted)
            card.purchased.connect(self.on_product_purchased)
            
            row = idx // 3
            col = idx % 3
            self.recs_grid.addWidget(card, row, col)

    def update_recommendations(self):
        # Fit model on current events
        self.recommender.fit()
        
        # Get hybrid recommendations
        recs = self.recommender.get_hybrid_recommendations(
            user_id=self.current_user_id,
            visual_similarities=self.visual_similarities,
            k=6
        )
        
        self.recs_lbl.setText("Recommended For You")
        self.clear_layout(self.recs_grid)
        
        for idx, (prod_id, prod, score) in enumerate(recs):
            card = ProductCard(prod, score=score, parent=self)
            card.viewed.connect(self.on_product_viewed)
            card.wishlisted.connect(self.on_product_wishlisted)
            card.purchased.connect(self.on_product_purchased)
            
            row = idx // 3
            col = idx % 3
            self.recs_grid.addWidget(card, row, col)

    def update_recently_viewed(self):
        self.clear_layout(self.recent_grid)
        events = get_user_events(self.current_user_id)
        
        # Filter for unique view events
        seen = set()
        view_product_ids = []
        for ev in events:
            if ev['event_type'] == 'view' and ev['product_id'] not in seen:
                seen.add(ev['product_id'])
                view_product_ids.append(ev['product_id'])
            if len(view_product_ids) >= 3:
                break
                
        conn = get_connection()
        cursor = conn.cursor()
        for idx, prod_id in enumerate(view_product_ids):
            cursor.execute("SELECT * FROM products WHERE product_id = ?", (prod_id,))
            prod = cursor.fetchone()
            if prod:
                card = ProductCard(dict(prod), parent=self)
                card.viewed.connect(self.on_product_viewed)
                card.wishlisted.connect(self.on_product_wishlisted)
                card.purchased.connect(self.on_product_purchased)
                self.recent_grid.addWidget(card, 0, idx)
        conn.close()

    def clear_search(self):
        self.search_image_path = None
        self.visual_similarities = []
        self.upload_widget.clear()
        self.search_input.clear()
        self.similar_lbl.hide()
        self.clear_layout(self.similar_grid)
        self.update_recommendations()

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    # Event handlers connecting user simulations to real-time database tracking
    @Slot(str)
    def on_product_viewed(self, product_id):
        track_event(self.current_user_id, product_id, 'view', dwell_time=15)
        self.update_recommendations()
        self.update_recently_viewed()

    @Slot(str)
    def on_product_wishlisted(self, product_id):
        track_event(self.current_user_id, product_id, 'wishlist')
        self.update_recommendations()

    @Slot(str)
    def on_product_purchased(self, product_id):
        track_event(self.current_user_id, product_id, 'purchase')
        self.update_recommendations()
        # Decrement stock in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock = MAX(0, stock - 1) WHERE product_id = ?", (product_id,))
        conn.commit()
        conn.close()
