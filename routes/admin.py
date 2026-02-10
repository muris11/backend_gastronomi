from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
import os
import shutil
from PIL import Image
import io
import json
from fastapi import UploadFile, File, Form
from typing import List, Optional
from dependencies.auth import verify_token
from config.database import db
from utils.validators import check_foto_profil_column, delete_old_profile_picture

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])

# Path untuk menyimpan file upload
SLIDER_UPLOAD_DIR = "uploads/slider"
TENTANG_KAMI_UPLOAD_DIR = "uploads/tentang_kami"
TIM_UPLOAD_DIR = "uploads/tim"
KONTAK_UPLOAD_DIR = "uploads/kontak"

# Buat direktori jika belum ada
os.makedirs(SLIDER_UPLOAD_DIR, exist_ok=True)
os.makedirs(TENTANG_KAMI_UPLOAD_DIR, exist_ok=True)
os.makedirs(TIM_UPLOAD_DIR, exist_ok=True)
os.makedirs(KONTAK_UPLOAD_DIR, exist_ok=True)

# Konfigurasi gambar
SLIDER_TARGET_WIDTH = 1200
SLIDER_TARGET_HEIGHT = 600
SLIDER_ASPECT_RATIO = SLIDER_TARGET_WIDTH / SLIDER_TARGET_HEIGHT
TIM_TARGET_WIDTH = 400
TIM_TARGET_HEIGHT = 400