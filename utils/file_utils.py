import os, re, shutil, unicodedata
from uuid import uuid4
from fastapi import UploadFile, HTTPException
import logging

logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove special characters"""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

def slugify(value: str) -> str:
    """Convert string to slug format"""
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-zA-Z0-9\s-]', '', value).strip().upper()
    parts = re.split(r'\s+', value)
    if not parts:
        return "ITEM"
    if len(parts) == 1:
        return parts[0][:6]
    return (parts[0][:3] + (parts[1][:3] if len(parts) > 1 else ''))[:6]

async def save_upload_file(file: UploadFile, subdirectory: str = "") -> str:
    """Save uploaded file to specified subdirectory and return relative path"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename tidak valid")
    
    # Buat subdirectory jika belum ada
    upload_path = os.path.join(UPLOAD_DIR, subdirectory)
    os.makedirs(upload_path, exist_ok=True)
    
    # Generate unique filename dengan format yang jelas
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    # Pastikan extension valid
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
    if file_extension not in valid_extensions:
        raise HTTPException(status_code=400, detail="Format file tidak didukung")
    
    # Generate nama file unik dengan timestamp
    import time
    timestamp = int(time.time())
    random_str = uuid4().hex[:8]
    filename = f"{timestamp}_{random_str}{file_extension}"
    filename = sanitize_filename(filename)
    
    # Full path untuk penyimpanan
    file_path = os.path.join(upload_path, filename)
    
    try:
        # Simpan file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Return relative path untuk database (dengan subdirectory)
        if subdirectory:
            relative_path = f"{subdirectory}/{filename}"
        else:
            relative_path = filename
        
        logger.info(f"File disimpan: {relative_path} di {file_path}")
        return relative_path
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {str(e)}")

def delete_file(filename: str):
    """Delete file from uploads directory"""
    if not filename:
        return
    
    try:
        # Bangun path lengkap
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        # Coba hapus file
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File dihapus: {file_path}")
            return True
            
        # Jika tidak ditemukan, coba cari di subdirectories
        logger.warning(f"File tidak ditemukan di path langsung: {file_path}")
        return False
        
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {str(e)}")
        return False

def generate_stok_units(start: int, jumlah: int, nama_barang: str, kondisi_default: str = "Baik"):
    """Generate stock units"""
    prefix = slugify(nama_barang)
    return [{"kode": f"{prefix}-{i:03d}", "kondisi": kondisi_default, "status": "Tersedia"} for i in range(start, start + jumlah)]