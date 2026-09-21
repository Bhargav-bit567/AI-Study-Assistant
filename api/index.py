import sys
import os

# Ensure project root is in sys.path for backend module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.main import app
