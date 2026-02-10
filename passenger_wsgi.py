import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

venv_python = os.getenv("PYTHON_INTERPRETER")
if venv_python and os.path.exists(venv_python) and sys.executable != venv_python:
    os.execl(venv_python, venv_python, *sys.argv)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

import importlib

ASGIMiddleware = importlib.import_module("a2wsgi").ASGIMiddleware
from main import app

application = ASGIMiddleware(app)
