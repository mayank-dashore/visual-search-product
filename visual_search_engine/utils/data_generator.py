import os
import random
import uuid
import numpy as np
import ssl
from PIL import Image, ImageDraw

# Silence HuggingFace Hub warnings and progress bars
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# Bypass SSL verification errors for model downloads
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass
from database.connection import get_connection
from database.schema import initialize_database
from models.embedder import EmbeddingGenerator
from retrieval.search_index import SearchIndex

DATASETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'datasets')
SYNTHETIC_DIR = os.path.join(DATASETS_DIR, 'synthetic')
TANISHQ_DIR = os.path.join(DATASETS_DIR, 'tanishq-jewellery-dataset')

def create_synthetic_image(category, filepath):
    """Draws a beautiful synthetic representation of jewelry using PIL."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img = Image.new('RGB', (226, 226), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Elegant jewelry colors
    gold_color = (212, 175, 55)
    silver_color = (192, 192, 192)
    gem_color = random.choice([(18, 97, 128), (220, 20, 60), (0, 128, 128)])
    
    color = random.choice([gold_color, silver_color])
    
    if category == 'Rings':
        # Draw a ring circle outline
        draw.ellipse([70, 70, 150, 150], outline=color, width=8)
        # Draw a gem on top
        draw.polygon([(100, 50), (120, 50), (125, 65), (95, 65)], fill=gem_color)
    elif category == 'Necklaces':
        # Draw a curved necklace
        draw.arc([40, 30, 180, 170], start=30, end=150, fill=color, width=10)
        # Draw a pendant hanging from the center
        draw.ellipse([100, 150, 120, 170], fill=gem_color)
    elif category == 'Earrings':
        # Draw two hanging earrings
        draw.line([70, 50, 70, 120], fill=color, width=4)
        draw.ellipse([60, 120, 80, 140], fill=gem_color)
        draw.line([150, 50, 150, 120], fill=color, width=4)
        draw.ellipse([140, 120, 160, 140], fill=gem_color)
    else: # Bangles/Bracelets
        draw.ellipse([60, 60, 160, 160], outline=color, width=12)
        # Add pattern details
        for i in range(0, 360, 30):
            rad = np.deg2rad(i)
            cx = 110 + int(50 * np.cos(rad))
            cy = 110 + int(50 * np.sin(rad))
            draw.ellipse([cx-4, cy-4, cx+4, cy+4], fill=gem_color)
            
    img.save(filepath)

def bootstrap_data(rebuild_index=True):
    """
    Initializes database tables, scans Tanishq or creates synthetic products,
    populates users and events, and optionally builds the vector search index.
    """
    print("Initializing Database tables...")
    initialize_database()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if we already have products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] > 0:
        print("Products already seeded in database.")
        conn.close()
        return
        
    categories = ['Rings', 'Necklaces', 'Earrings', 'Bangles']
    product_records = []
    
    # Check if Tanishq Dataset exists locally
    tanishq_found = False
    if os.path.exists(TANISHQ_DIR):
        print(f"Found Tanishq Jewellery dataset directory at {TANISHQ_DIR}")
        # Search for images recursively in folders
        for root, dirs, files in os.walk(TANISHQ_DIR):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(root, file)
                    # Determine category from folder name or default
                    category = 'Necklaces'
                    for cat in categories:
                        # Match plural/singular forms like "ring" to "Rings"
                        stem = cat.lower()[:-1] if cat.lower().endswith('s') else cat.lower()
                        if stem in root.lower() or stem in file.lower():
                            category = cat
                            break
                    
                    import hashlib
                    clean_rel = img_path.replace("\\", "/").lower()
                    if "datasets/" in clean_rel:
                        clean_rel = clean_rel[clean_rel.index("datasets/"):]
                    h = hashlib.md5(clean_rel.encode('utf-8')).hexdigest()
                    prod_id = f"prod_{h[:12]}"
                    import re
                    name_part = os.path.splitext(file)[0]
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
                        price = round(random.uniform(500, 10000), 2)
                    if stock is None or stock < 0:
                        stock = random.randint(2, 20)
                        
                    clean_name = name_part.split('_')[0].split('-')[0].replace('_', ' ').replace('-', ' ').title()
                    name = f"Tanishq {category[:-1] if category.endswith('s') else category} {clean_name}"
                    
                    product_records.append((prod_id, name, category, price, img_path, stock))
                    tanishq_found = True
                    
    if not tanishq_found:
        print("Tanishq dataset not found or empty. Generating 40 high-quality synthetic products...")
        os.makedirs(SYNTHETIC_DIR, exist_ok=True)
        for i in range(40):
            category = random.choice(categories)
            prod_id = f"prod_synth_{i:03d}"
            name = f"Aura {category[:-1] if category.endswith('s') else category} - {random.choice(['Gold', 'Silver', 'Platinum', 'Rose Gold'])}"
            price = round(random.uniform(150, 5000), 2)
            stock = random.randint(1, 15)
            img_path = os.path.join(SYNTHETIC_DIR, f"{prod_id}.png")
            
            create_synthetic_image(category, img_path)
            product_records.append((prod_id, name, category, price, img_path, stock))

    # Insert products into DB
    cursor.executemany(
        "INSERT INTO products (product_id, name, category, price, image_path, stock) VALUES (?, ?, ?, ?, ?, ?)",
        product_records
    )
    print(f"Successfully inserted {len(product_records)} products.")

    # Create Users
    users_records = [
        ('user_1', 'Mayank Dashore', 'Premium Buyer'),
        ('user_2', 'Alice Smith', 'Bargain Hunter'),
        ('user_3', 'Bob Johnson', 'Casual Browser'),
        ('user_4', 'Claire Taylor', 'Gift Shopper')
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO users (user_id, name, profile_type) VALUES (?, ?, ?)",
        users_records
    )
    print("Users seeded.")

    # Seed User events to train the Recommendation model
    events_to_seed = []
    event_types = ['view', 'click', 'wishlist', 'purchase']
    weights = [0.6, 0.25, 0.1, 0.05] # Probability distribution of actions
    
    # Dynamically extract actually present categories
    actual_categories = list(set([p[2] for p in product_records]))
    
    for u_id, _, profile in users_records:
        # Each user prefers a certain category from the available list
        preferred_cat = random.choice(actual_categories) if actual_categories else 'Necklaces'
        user_products = [p for p in product_records if p[2] == preferred_cat]
        other_products = [p for p in product_records if p[2] != preferred_cat]
        
        # 30-50 actions per user
        for _ in range(random.randint(30, 50)):
            # 70% chance of acting on preferred category
            if random.random() < 0.7 and user_products:
                prod = random.choice(user_products)
            elif other_products:
                prod = random.choice(other_products)
            else:
                prod = random.choice(product_records)
                
            p_id = prod[0]
            etype = random.choices(event_types, weights=weights)[0]
            dwell_time = random.randint(5, 120) if etype == 'view' else 0
            
            events_to_seed.append((u_id, p_id, etype, dwell_time))
            
    cursor.executemany(
        "INSERT INTO user_events (user_id, product_id, event_type, dwell_time) VALUES (?, ?, ?, ?)",
        events_to_seed
    )
    conn.commit()
    conn.close()
    print(f"Logged {len(events_to_seed)} synthetic user interaction events.")

    if rebuild_index:
        rebuild_vector_search_index()

def rebuild_vector_search_index():
    """Generates embeddings for all products and inserts them into the FAISS/retrieval index."""
    print("Generating product embeddings and building vector index (this may take a moment)...")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, image_path FROM products")
    rows = cursor.fetchall()
    conn.close()
    
    embedder = EmbeddingGenerator()
    index = SearchIndex(dimension=embedder.get_dim())
    index.clear()
    
    success_count = 0
    for prod_id, img_path in rows:
        try:
            # Read and process image
            if not os.path.exists(img_path):
                continue
            pil_img = Image.open(img_path).convert('RGB')
            # Generate embedding
            emb = embedder.get_embedding(pil_img)
            index.add_product(prod_id, emb)
            success_count += 1
        except Exception as e:
            print(f"Skipping product {prod_id} due to embedding error: {e}")
            
    if success_count > 0:
        index.save()
        print(f"Successfully generated embeddings and built index for {success_count} products.")
    else:
        print("Warning: No product embeddings generated.")

if __name__ == '__main__':
    bootstrap_data()
