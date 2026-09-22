"""WSGI entry point for PythonAnywhere deployment."""

import os
import sys

# Add project root to path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from a2wsgi import ASGI2WSGI
from backend.app.main import app

application = ASGI2WSGI(app)
