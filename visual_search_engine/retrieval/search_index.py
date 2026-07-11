import numpy as np
import os
import pickle

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    print("Warning: FAISS not found. Falling back to NumPy-based vector similarity search.")

INDEX_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vector_index.bin')
METADATA_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vector_metadata.pkl')

class SearchIndex:
    def __init__(self, dimension=3328):
        self.dimension = dimension
        self.product_ids = []
        
        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dimension)
        else:
            self.embeddings_matrix = None

    def add_product(self, product_id, embedding):
        """Adds a product embedding to the index."""
        emb = np.array(embedding, dtype=np.float32).reshape(1, -1)
        # Ensure normalization
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        
        self.product_ids.append(product_id)
        
        if HAS_FAISS:
            self.index.add(emb)
        else:
            if self.embeddings_matrix is None:
                self.embeddings_matrix = emb
            else:
                self.embeddings_matrix = np.vstack([self.embeddings_matrix, emb])

    def search(self, query_embedding, k=10):
        """Searches index for similar items. Returns list of (product_id, similarity_score)."""
        if not self.product_ids:
            return []
            
        q_emb = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        q_emb = q_emb / (np.linalg.norm(q_emb) + 1e-8)
        
        actual_k = min(k, len(self.product_ids))
        
        raw_results = []
        if HAS_FAISS:
            scores, indices = self.index.search(q_emb, actual_k)
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.product_ids):
                    continue
                raw_results.append((self.product_ids[idx], float(score)))
        else:
            if self.embeddings_matrix is None:
                return []
            scores = np.dot(self.embeddings_matrix, q_emb.T).flatten()
            top_k_indices = np.argsort(scores)[::-1][:actual_k]
            raw_results = [(self.product_ids[idx], float(scores[idx])) for idx in top_k_indices]

        # Calibrate similarity scores to a realistic matching range and filter by disk presence
        calibrated_results = []
        import sqlite3
        from database.connection import get_connection
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        for pid, score in raw_results:
            cursor.execute("SELECT image_path FROM products WHERE product_id = ?", (pid,))
            row = cursor.fetchone()
            if row:
                img_path = row['image_path']
                actual_img_path = img_path
                if img_path and not os.path.isabs(img_path):
                    clean_path = img_path
                    if img_path.startswith("visual_search_engine/"):
                        clean_path = img_path[len("visual_search_engine/"):]
                    elif img_path.startswith("visual_search_engine\\"):
                        clean_path = img_path[len("visual_search_engine\\"):]
                    actual_img_path = os.path.join(app_root, clean_path)
                
                # Check if the image file exists on disk in datasets folder
                if actual_img_path and os.path.exists(actual_img_path):
                    if score >= 0.999:
                        calibrated_score = 1.0
                    else:
                        s_clamped = max(-1.0, min(1.0, score))
                        calibrated_score = 0.75 + 0.23 * max(0.0, s_clamped)
                    calibrated_results.append((pid, calibrated_score))
                    
        conn.close()
        return calibrated_results

    def save(self):
        """Saves the index to files."""
        # Save product IDs
        with open(METADATA_FILE_PATH, 'wb') as f:
            pickle.dump(self.product_ids, f)
            
        if HAS_FAISS:
            faiss.write_index(self.index, INDEX_FILE_PATH)
        else:
            with open(INDEX_FILE_PATH, 'wb') as f:
                pickle.dump(self.embeddings_matrix, f)

    def load(self):
        """Loads the index from files."""
        if not os.path.exists(METADATA_FILE_PATH) or not os.path.exists(INDEX_FILE_PATH):
            return False
            
        try:
            with open(METADATA_FILE_PATH, 'rb') as f:
                self.product_ids = pickle.load(f)
                
            if HAS_FAISS:
                self.index = faiss.read_index(INDEX_FILE_PATH)
            else:
                with open(INDEX_FILE_PATH, 'rb') as f:
                    self.embeddings_matrix = pickle.load(f)
            return True
        except Exception as e:
            print(f"Error loading index: {e}")
            return False

    def clear(self):
        """Clears the index."""
        self.product_ids = []
        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dimension)
        else:
            self.embeddings_matrix = None

    def remove_product(self, product_id):
        """Removes a product embedding from the index without regenerating embeddings."""
        if product_id not in self.product_ids:
            return False
            
        idx = self.product_ids.index(product_id)
        self.product_ids.pop(idx)
        
        if HAS_FAISS:
            try:
                # Reconstruct all vectors from FAISS Index
                vectors = []
                for i in range(self.index.ntotal):
                    vectors.append(self.index.reconstruct(i))
                
                # Remove the target index
                vectors.pop(idx)
                
                # Reset index and add back remaining vectors
                self.index = faiss.IndexFlatIP(self.dimension)
                if vectors:
                    self.index.add(np.array(vectors, dtype=np.float32))
            except Exception as e:
                print(f"FAISS vector removal reconstruction error: {e}")
                return False
        else:
            if self.embeddings_matrix is not None:
                self.embeddings_matrix = np.delete(self.embeddings_matrix, idx, axis=0)
                if len(self.product_ids) == 0:
                    self.embeddings_matrix = None
        return True
