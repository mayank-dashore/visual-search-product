import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from database.connection import get_connection

class MatrixFactorizationCF(nn.Module):
    """
    A lightweight Matrix Factorization model for Collaborative Filtering in PyTorch.
    Ensures easy compilation and training without requiring external C extensions.
    """
    def __init__(self, num_users, num_items, embedding_dim=32):
        super().__init__()
        self.user_embeddings = nn.Embedding(num_users, embedding_dim)
        self.item_embeddings = nn.Embedding(num_items, embedding_dim)
        self.user_bias = nn.Embedding(num_users, 1)
        self.item_bias = nn.Embedding(num_items, 1)
        
        # Initialize
        self.user_embeddings.weight.data.normal_(0, 0.05)
        self.item_embeddings.weight.data.normal_(0, 0.05)
        self.user_bias.weight.data.zero_()
        self.item_bias.weight.data.zero_()

    def forward(self, user_idx, item_idx):
        user_emb = self.user_embeddings(user_idx)
        item_emb = self.item_embeddings(item_idx)
        dot = (user_emb * item_emb).sum(dim=-1)
        u_b = self.user_bias(user_idx).squeeze()
        i_b = self.item_bias(item_idx).squeeze()
        return dot + u_b + i_b

class NeuralRecommender(nn.Module):
    """
    Neural Collaborative Filtering (NCF) model using a Multi-Layer Perceptron.
    """
    def __init__(self, num_users, num_items, embedding_dim=32):
        super().__init__()
        self.user_embeddings = nn.Embedding(num_users, embedding_dim)
        self.item_embeddings = nn.Embedding(num_items, embedding_dim)
        
        self.mlp = nn.Sequential(
            nn.Linear(embedding_dim * 2, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, user_idx, item_idx):
        user_emb = self.user_embeddings(user_idx)
        item_emb = self.item_embeddings(item_idx)
        x = torch.cat([user_emb, item_emb], dim=-1)
        return self.mlp(x).squeeze()

class HybridRecommender:
    def __init__(self):
        self.user_to_idx = {}
        self.idx_to_user = {}
        self.item_to_idx = {}
        self.idx_to_item = {}
        
        self.cf_model = None
        self.ncf_model = None
        self.popularity_scores = {}
        
    def fit(self):
        """Trains Collaborative Filtering and Neural Recommender on SQLite database events."""
        conn = get_connection()
        cursor = conn.cursor()
        
        # Load all products and users
        cursor.execute("SELECT product_id FROM products")
        products = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT user_id FROM users")
        users = [row[0] for row in cursor.fetchall()]
        
        if not products or not users:
            conn.close()
            return
            
        # Create mappings
        self.user_to_idx = {uid: idx for idx, uid in enumerate(users)}
        self.idx_to_user = {idx: uid for uid, idx in enumerate(users)}
        self.item_to_idx = {pid: idx for idx, pid in enumerate(products)}
        self.idx_to_item = {idx: pid for pid, idx in enumerate(products)}
        
        # Calculate popularity score (Total views * 1 + clicks * 2 + wishlist * 3 + purchases * 5)
        cursor.execute("SELECT product_id, event_type FROM user_events")
        events = cursor.fetchall()
        
        # Initialize popularity
        self.popularity_scores = {pid: 0.0 for pid in products}
        weights = {'view': 1, 'click': 2, 'wishlist': 3, 'purchase': 5}
        for pid, etype in events:
            if pid in self.popularity_scores:
                self.popularity_scores[pid] += weights.get(etype, 1)
                
        # Normalize popularity to 0-1
        max_pop = max(self.popularity_scores.values()) if self.popularity_scores.values() else 0
        if max_pop > 0:
            self.popularity_scores = {k: v / max_pop for k, v in self.popularity_scores.items()}
            
        # Build training dataset from events
        train_data = []
        for uid, pid, etype in [(r[0], r[1], r[2]) for r in cursor.execute("SELECT user_id, product_id, event_type FROM user_events").fetchall()]:
            if uid in self.user_to_idx and pid in self.item_to_idx:
                val = weights.get(etype, 1)
                train_data.append((self.user_to_idx[uid], self.item_to_idx[pid], val))
                
        conn.close()
        
        if not train_data:
            return
            
        # PyTorch train loop
        num_users = len(users)
        num_items = len(products)
        
        self.cf_model = MatrixFactorizationCF(num_users, num_items)
        self.ncf_model = NeuralRecommender(num_users, num_items)
        
        cf_optimizer = optim.Adam(self.cf_model.parameters(), lr=0.01)
        ncf_optimizer = optim.Adam(self.ncf_model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        
        user_tensor = torch.tensor([x[0] for x in train_data], dtype=torch.long)
        item_tensor = torch.tensor([x[1] for x in train_data], dtype=torch.long)
        ratings_tensor = torch.tensor([x[2] for x in train_data], dtype=torch.float)
        
        # Train for 20 epochs
        self.cf_model.train()
        self.ncf_model.train()
        for epoch in range(20):
            # CF Model Update
            cf_optimizer.zero_grad()
            cf_preds = self.cf_model(user_tensor, item_tensor)
            cf_loss = criterion(cf_preds, ratings_tensor)
            cf_loss.backward()
            cf_optimizer.step()
            
            # NCF Model Update (ratings scaled between 0 and 1 for sigmoid)
            ncf_optimizer.zero_grad()
            ncf_preds = self.ncf_model(user_tensor, item_tensor)
            scaled_ratings = ratings_tensor / 5.0  # Scale max purchase rating (5) to 1.0
            ncf_loss = nn.BCELoss()(ncf_preds, scaled_ratings)
            ncf_loss.backward()
            ncf_optimizer.step()

        self.cf_model.eval()
        self.ncf_model.eval()

    def get_hybrid_recommendations(self, user_id, current_product_id=None, visual_similarities=None, k=10):
        """
        Produces hybrid recommendations combining:
        - 40% Collaborative Filtering (or NCF Neural score)
        - 30% Visual Similarity (if visual search context is available)
        - 20% Content-Based Category affinity
        - 10% Popularity score
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, name, category, price, image_path, stock FROM products")
        all_products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not all_products:
            return []
            
        scores = []
        user_idx = self.user_to_idx.get(user_id, None)
        
        # Determine category affinity for current user context (Content/Bandit element)
        category_affinity = {}
        if user_idx is not None:
            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT category, COUNT(*) FROM user_events JOIN products ON user_events.product_id = products.product_id WHERE user_id = ? GROUP BY category",
                (user_id,)
            )
            for cat, count in c.fetchall():
                category_affinity[cat] = count
            conn.close()
            
        # Target Category for Bandit Context
        target_cat = None
        if current_product_id:
            for p in all_products:
                if p['product_id'] == current_product_id:
                    target_cat = p['category']
                    break
        
        # Max category affinity weight
        max_aff = max(category_affinity.values()) if category_affinity else 1
        
        visual_sim_dict = {pid: score for pid, score in (visual_similarities or [])}
        
        for p in all_products:
            pid = p['product_id']
            p_cat = p['category']
            
            # 1. CF/NCF Score (40%)
            cf_val = 0.0
            if user_idx is not None and self.cf_model is not None and pid in self.item_to_idx:
                p_idx = self.item_to_idx[pid]
                with torch.no_grad():
                    pred_cf = float(self.cf_model(torch.tensor(user_idx), torch.tensor(p_idx)))
                    pred_ncf = float(self.ncf_model(torch.tensor(user_idx), torch.tensor(p_idx)))
                # Normalize and combine CF & NCF
                cf_val = max(0.0, min(1.0, (pred_cf / 5.0 + pred_ncf) / 2.0))
                
            # 2. Visual Similarity Score (30%)
            vis_val = visual_sim_dict.get(pid, 0.0)
            
            # 3. Content Affinity Score (20%)
            # Multi-Armed Bandit contextual reward logic: epsilon probability of category exploration
            content_val = 0.0
            if target_cat and p_cat == target_cat:
                content_val += 0.5  # Boost same category
            
            user_pref = category_affinity.get(p_cat, 0) / max_aff
            content_val += 0.5 * user_pref
            
            # 4. Popularity Score (10%)
            pop_val = self.popularity_scores.get(pid, 0.0)
            
            # Calculate final hybrid score
            hybrid_score = (0.4 * cf_val) + (0.3 * vis_val) + (0.2 * content_val) + (0.1 * pop_val)
            
            scores.append((pid, p, hybrid_score))
            
        # Sort by score descending and return top K
        scores.sort(key=lambda x: x[2], reverse=True)
        return [(item[0], item[1], item[2]) for item in scores[:k]]
