import re
import os
from models.enums import KondisiBarang, StatusPeminjaman, StatusUnit
from config.database import db
import logging

logger = logging.getLogger(__name__)

def validate_email(email: str) -> bool:
    """Validasi format email"""
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_regex, email))

def validate_kondisi_barang(kondisi: str) -> bool:
    """Validasi apakah kondisi barang valid"""
    kondisi_valid = [k.value for k in KondisiBarang]
    return kondisi in kondisi_valid

def validate_status_peminjaman(status: str) -> bool:
    """Validasi status peminjaman"""
    status_valid = [s.value for s in StatusPeminjaman]
    return status in status_valid

def validate_status_unit(status: str) -> bool:
    """Validasi status unit"""
    status_valid = [s.value for s in StatusUnit]
    return status in status_valid

def normalize_kondisi(kondisi: str) -> str:
    """Normalisasi kondisi untuk kompatibilitas"""
    kondisi_mapping = {
        "Kurang Baik": "Rusak Ringan",
        "Rusak": "Rusak Berat",
        "Maintenance": "Rusak Berat"
    }
    return kondisi_mapping.get(kondisi, kondisi)

# ===== FUNGSI BARU UNTUK ADMIN =====

def check_foto_profil_column():
    """Cek apakah kolom foto_profil ada di database"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SHOW COLUMNS FROM users LIKE 'foto_profil'")
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking foto_profil column: {str(e)}")
        return False
    finally:
        cursor.close()
        connection.close()

def delete_old_profile_picture(user_id: int):
    """Menghapus foto profil lama"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom foto_profil ada
        cursor.execute("SHOW COLUMNS FROM users LIKE 'foto_profil'")
        column_exists = cursor.fetchone()
        
        if not column_exists:
            return
            
        cursor.execute("SELECT foto_profil FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if user and user.get('foto_profil'):
            old_file_path = os.path.join("uploads/profile_pictures", user['foto_profil'])
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
                logger.info(f"Deleted old profile picture for user {user_id}: {user['foto_profil']}")
    except Exception as e:
        logger.error(f"Error deleting old profile picture: {str(e)}")
    finally:
        cursor.close()
        connection.close()

def validate_phone(phone: str) -> bool:
    """Validasi nomor telepon"""
    if not phone:
        return True  # No phone is acceptable
    
    pattern = r'^\+?[\d\s\-\(\)]{10,}$'
    return bool(re.match(pattern, phone))

def validate_file_upload(filename: str, allowed_extensions: set, max_size: int) -> dict:
    """
    Validasi file upload
    Returns: dict dengan keys 'valid' (bool) dan 'message' (str)
    """
    if not filename:
        return {'valid': False, 'message': 'File tidak ditemukan'}
    
    # Cek ekstensi file
    file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if file_extension not in allowed_extensions:
        return {'valid': False, 'message': f'Format file tidak didukung. Gunakan {", ".join(allowed_extensions)}'}
    
    return {'valid': True, 'message': 'File valid'}

def sanitize_input(text: str) -> str:
    """Membersihkan input dari karakter berbahaya"""
    if not text:
        return text
    
    # Hapus tag HTML
    clean_text = re.sub(r'<[^>]*>', '', text)
    
    # Escape karakter khusus
    clean_text = clean_text.replace("'", "''").replace('"', '""')
    
    return clean_text.strip()

def validate_password(password: str) -> dict:
    """
    Validasi kekuatan password
    Returns: dict dengan keys 'valid' (bool) dan 'message' (str)
    """
    if len(password) < 6:
        return {'valid': False, 'message': 'Password minimal 6 karakter'}
    
    # Cek kompleksitas password (opsional)
    if password.isnumeric():
        return {'valid': False, 'message': 'Password harus mengandung huruf dan angka'}
    
    return {'valid': True, 'message': 'Password valid'}

def validate_username(username: str) -> dict:
    """
    Validasi format username
    Returns: dict dengan keys 'valid' (bool) dan 'message' (str)
    """
    if len(username) < 3:
        return {'valid': False, 'message': 'Username minimal 3 karakter'}
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return {'valid': False, 'message': 'Username hanya boleh mengandung huruf, angka, dan underscore'}
    
    return {'valid': True, 'message': 'Username valid'}

def check_last_login_column():
    """Cek apakah kolom last_login ada di database"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SHOW COLUMNS FROM users LIKE 'last_login'")
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking last_login column: {str(e)}")
        return False
    finally:
        cursor.close()
        connection.close()

