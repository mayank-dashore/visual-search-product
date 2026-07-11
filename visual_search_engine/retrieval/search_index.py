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

        # Calibrate similarity scores to a realistic matching range
        calibrated_results = []
        for pid, score in raw_results:
            if score >= 0.999:
                calibrated_score = 1.0
            else:
                s_clamped = max(-1.0, min(1.0, score))
                calibrated_score = 0.75 + 0.23 * max(0.0, s_clamped)
            calibrated_results.append((pid, calibrated_score))
            
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
