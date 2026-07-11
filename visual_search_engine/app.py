import sys
import os
import ssl

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

# Adjust path to make visual_search_engine imports work seamlessly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
from utils.data_generator import bootstrap_data

def main():
    # Bootstrap data if first time running
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
    if not os.path.exists(db_path):
        print("Database not found. Bootstrapping synthetic jewelry dataset...")
        bootstrap_data(rebuild_index=True)
    
    # Launch application
    app = QApplication(sys.argv)
    
    # Set app window style preference
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
