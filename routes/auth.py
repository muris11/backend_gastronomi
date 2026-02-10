from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from models.base_models import RegisterRequest, ProfileUpdateRequest, PasswordUpdateRequest
from dependencies.auth import verify_token
from config.database import db
from utils.validators import validate_email
import logging
from datetime import datetime
from uuid import uuid4
import os
import shutil
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Authentication"])

# Konfigurasi upload foto
UPLOAD_DIR = "uploads/profile_pictures"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Pastikan direktori upload ada
os.makedirs(UPLOAD_DIR, exist_ok=True)

def allowed_file(filename: str) -> bool:
    """Cek apakah ekstensi file diizinkan"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_picture(file: UploadFile, user_id: int) -> str:
    """Menyimpan foto profil dan mengembalikan nama file"""
    # Hapus foto lama jika ada
    delete_old_profile_picture(user_id)
    
    # Generate nama file baru
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    filename = f"profile_{user_id}_{uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Simpan file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return filename

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
            old_file_path = os.path.join(UPLOAD_DIR, user['foto_profil'])
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
    except Exception as e:
        logger.error(f"Error deleting old profile picture: {str(e)}")
    finally:
        cursor.close()
        connection.close()

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

@router.post("/register")
def register(register_data: RegisterRequest):
    """
    Endpoint untuk registrasi user baru.
    Role default adalah 'user'.
    """
    if not register_data.username or not register_data.password:
        raise HTTPException(status_code=400, detail="Username dan password harus diisi")
    
    if len(register_data.username) < 3:
        raise HTTPException(status_code=400, detail="Username minimal 3 karakter")
    
    if len(register_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password minimal 6 karakter")
    
    if register_data.email and not validate_email(register_data.email):
        raise HTTPException(status_code=400, detail="Format email tidak valid")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah username sudah digunakan
        cursor.execute("SELECT id FROM users WHERE username = %s", (register_data.username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="Username sudah digunakan")
        
        # Cek apakah email sudah digunakan
        if register_data.email:
            cursor.execute("SELECT id FROM users WHERE email = %s", (register_data.email,))
            existing_email = cursor.fetchone()
            
            if existing_email:
                raise HTTPException(status_code=400, detail="Email sudah digunakan")
        
        # Cek apakah kolom foto_profil ada
        foto_profil_column_exists = check_foto_profil_column()
        
        # Insert user baru
        if foto_profil_column_exists:
            cursor.execute(
                """INSERT INTO users 
                (username, password, nama_lengkap, email, no_telepon, alamat, role, created_at, foto_profil) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    register_data.username,
                    register_data.password,
                    register_data.nama_lengkap,
                    register_data.email,
                    register_data.no_telepon,
                    register_data.alamat,
                    'user',  # Default role adalah 'user'
                    datetime.now(),
                    None  # foto_profil default null
                )
            )
        else:
            cursor.execute(
                """INSERT INTO users 
                (username, password, nama_lengkap, email, no_telepon, alamat, role, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    register_data.username,
                    register_data.password,
                    register_data.nama_lengkap,
                    register_data.email,
                    register_data.no_telepon,
                    register_data.alamat,
                    'user',
                    datetime.now()
                )
            )
        
        connection.commit()
        
        # Log registrasi berhasil
        logger.info(f"User registered: {register_data.username}")
        
        return {
            "message": "Registrasi berhasil",
            "username": register_data.username,
            "role": "user"
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error during registration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saat registrasi: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint login untuk user biasa dan admin.
    Sama untuk semua user, bedanya hanya di role.
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom foto_profil dan last_login ada
        foto_profil_column_exists = check_foto_profil_column()
        
        # Cek apakah kolom last_login ada
        cursor.execute("SHOW COLUMNS FROM users LIKE 'last_login'")
        last_login_column_exists = cursor.fetchone() is not None
        
        # Query user berdasarkan username dan password
        if foto_profil_column_exists:
            cursor.execute("SELECT *, foto_profil FROM users WHERE username = %s AND password = %s", 
                          (form_data.username, form_data.password))
        else:
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", 
                          (form_data.username, form_data.password))
                          
        user = cursor.fetchone()
        
        if user:
            # ✅ UPDATE LAST LOGIN - PASTIKAN INI SELALU DIJALANKAN
            if last_login_column_exists:
                cursor.execute(
                    "UPDATE users SET last_login = %s WHERE id = %s",
                    (datetime.now(), user['id'])
                )
                connection.commit()
                logger.info(f"Updated last_login for user {user['id']} at {datetime.now()}")
            
            # Log login berhasil dengan role
            logger.info(f"Login successful - User: {user['username']}, Role: {user['role']}")
            
            # Generate token sederhana
            token = f"1|{user['role']}|{user['username']}|{uuid4().hex}"
            
            # Response data
            response_data = {
                "access_token": token, 
                "token_type": "bearer", 
                "role": user['role'], 
                "username": user['username'],
                "nama_lengkap": user.get('nama_lengkap', ''),
                "email": user.get('email', ''),
                "user_id": user['id']
            }
            
            # Tambahkan foto_profil jika kolom ada
            if foto_profil_column_exists:
                response_data["foto_profil"] = user.get('foto_profil')
            
            # Log khusus untuk admin login
            if user['role'] == 'admin':
                logger.warning(f"⚠️ ADMIN LOGIN DETECTED - User: {user['username']}")
            
            return response_data
        
        # Jika user tidak ditemukan
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(status_code=401, detail="Username atau password salah")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        cursor.close()
        connection.close()

@router.post("/logout")
def logout(
    logout_data: dict = None,
    token: dict = Depends(verify_token)
):
    """
    Endpoint logout dengan update last_login.
    Bisa diakses oleh user dan admin.
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom last_login ada
        cursor.execute("SHOW COLUMNS FROM users LIKE 'last_login'")
        last_login_column_exists = cursor.fetchone() is not None
        
        # ✅ UPDATE LAST LOGIN SAAT LOGOUT
        if last_login_column_exists:
            cursor.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (datetime.now(), token["user_id"])
            )
            connection.commit()
            logger.info(f"User logout - User ID: {token['user_id']} at {datetime.now()}")
        
        return {
            "message": "Logout berhasil",
            "user_id": token["user_id"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        # Tetap return success meskipun update gagal
        return {
            "message": "Logout berhasil",
            "user_id": token["user_id"],
            "timestamp": datetime.now().isoformat()
        }
    finally:
        cursor.close()
        connection.close()

@router.get("/profile")
def get_profile(token: dict = Depends(verify_token)):
    """
    Mendapatkan profile user yang sedang login.
    Bisa diakses oleh user dan admin.
    """
    try:
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Cek apakah kolom foto_profil ada
        foto_profil_column_exists = check_foto_profil_column()
        
        # Query user berdasarkan ID
        if foto_profil_column_exists:
            cursor.execute(
                "SELECT id, username, nama_lengkap, email, no_telepon, alamat, role, created_at, updated_at, foto_profil FROM users WHERE id = %s",
                (token["user_id"],)
            )
        else:
            cursor.execute(
                "SELECT id, username, nama_lengkap, email, no_telepon, alamat, role, created_at, updated_at FROM users WHERE id = %s",
                (token["user_id"],)
            )
            
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
        
        # Siapkan response data
        profile_data = {
            "id": user["id"],
            "username": user["username"],
            "nama_lengkap": user["nama_lengkap"],
            "email": user["email"],
            "no_telepon": user["no_telepon"],
            "alamat": user["alamat"],
            "role": user["role"],
            "created_at": user["created_at"],
            "updated_at": user.get("updated_at")
        }
        
        # Tambahkan foto_profil jika kolom ada
        if foto_profil_column_exists:
            profile_data["foto_profil"] = user.get("foto_profil")
        
        return profile_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data profile: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/profile")
def update_profile(
    profile_data: ProfileUpdateRequest,
    token: dict = Depends(verify_token)
):
    """
    Update profile user.
    Bisa diakses oleh user dan admin.
    """
    if not profile_data.nama_lengkap or not profile_data.email:
        raise HTTPException(status_code=400, detail="Nama lengkap dan email harus diisi")
    
    if not validate_email(profile_data.email):
        raise HTTPException(status_code=400, detail="Format email tidak valid")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah email sudah digunakan oleh user lain
        cursor.execute(
            "SELECT id FROM users WHERE email = %s AND id != %s", 
            (profile_data.email, token["user_id"])
        )
        existing_email = cursor.fetchone()
        
        if existing_email:
            raise HTTPException(status_code=400, detail="Email sudah digunakan oleh user lain")
        
        # Update data user
        cursor.execute(
            """UPDATE users 
            SET nama_lengkap = %s, email = %s, no_telepon = %s, alamat = %s, updated_at = %s 
            WHERE id = %s""",
            (
                profile_data.nama_lengkap,
                profile_data.email,
                profile_data.no_telepon,
                profile_data.alamat,
                datetime.now(),
                token["user_id"]
            )
        )
        
        connection.commit()
        
        # Ambil data terbaru setelah update
        foto_profil_column_exists = check_foto_profil_column()
        
        if foto_profil_column_exists:
            cursor.execute(
                "SELECT id, username, nama_lengkap, email, no_telepon, alamat, role, created_at, foto_profil FROM users WHERE id = %s",
                (token["user_id"],)
            )
        else:
            cursor.execute(
                "SELECT id, username, nama_lengkap, email, no_telepon, alamat, role, created_at FROM users WHERE id = %s",
                (token["user_id"],)
            )
            
        updated_user = cursor.fetchone()
        
        logger.info(f"Profile updated - User ID: {token['user_id']}")
        
        return {
            "message": "Profile berhasil diperbarui",
            "profile": updated_user
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error memperbarui profile: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/profile/password")
def update_password(
    password_data: PasswordUpdateRequest,
    token: dict = Depends(verify_token)
):
    """
    Update password user.
    Bisa diakses oleh user dan admin.
    """
    if not password_data.password_lama or not password_data.password_baru:
        raise HTTPException(status_code=400, detail="Password lama dan password baru harus diisi")
    
    if len(password_data.password_baru) < 6:
        raise HTTPException(status_code=400, detail="Password baru minimal 6 karakter")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Verifikasi password lama
        cursor.execute(
            "SELECT password FROM users WHERE id = %s", 
            (token["user_id"],)
        )
        user = cursor.fetchone()
        
        if not user or user['password'] != password_data.password_lama:
            raise HTTPException(status_code=400, detail="Password lama tidak sesuai")
        
        # Update password baru
        cursor.execute(
            "UPDATE users SET password = %s, updated_at = %s WHERE id = %s",
            (password_data.password_baru, datetime.now(), token["user_id"])
        )
        
        connection.commit()
        
        logger.info(f"Password changed - User ID: {token['user_id']}")
        
        return {
            "message": "Password berhasil diubah"
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating password: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengubah password: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/profile/upload-photo")
async def upload_profile_photo(
    file: UploadFile = File(...),
    token: dict = Depends(verify_token)
):
    """Upload foto profil"""
    try:
        # Cek apakah kolom foto_profil ada
        if not check_foto_profil_column():
            raise HTTPException(status_code=500, detail="Fitur foto profil belum tersedia di database")
        
        # Validasi file
        if not file:
            raise HTTPException(status_code=400, detail="File tidak ditemukan")
        
        if not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail="Format file tidak didukung. Gunakan PNG, JPG, atau JPEG")
        
        # Cek ukuran file
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Ukuran file terlalu besar. Maksimal 5MB")
        
        # Simpan file
        filename = save_profile_picture(file, token["user_id"])
        
        # Update database
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "UPDATE users SET foto_profil = %s, updated_at = %s WHERE id = %s",
            (filename, datetime.now(), token["user_id"])
        )
        
        connection.commit()
        
        logger.info(f"Profile photo uploaded - User ID: {token['user_id']}, File: {filename}")
        
        return {
            "message": "Foto profil berhasil diupload",
            "filename": filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile photo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupload foto profil: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/profile/photo")
def delete_profile_photo(token: dict = Depends(verify_token)):
    """Hapus foto profil"""
    try:
        # Cek apakah kolom foto_profil ada
        if not check_foto_profil_column():
            raise HTTPException(status_code=500, detail="Fitur foto profil belum tersedia di database")
        
        # Hapus file foto lama
        delete_old_profile_picture(token["user_id"])
        
        # Update database
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "UPDATE users SET foto_profil = NULL, updated_at = %s WHERE id = %s",
            (datetime.now(), token["user_id"])
        )
        
        connection.commit()
        
        logger.info(f"Profile photo deleted - User ID: {token['user_id']}")
        
        return {
            "message": "Foto profil berhasil dihapus"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile photo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus foto profil: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Endpoint untuk mengakses file foto profil
@router.get("/uploads/profile_pictures/{filename}")
def get_profile_picture(filename: str):
    """Mengembalikan file foto profil"""
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path)

# 🔥 ENDPOINT TAMBAHAN UNTUK CHECK AUTH STATUS
@router.get("/auth/check")
def check_auth_status(token: dict = Depends(verify_token)):
    """
    Endpoint untuk mengecek status autentikasi.
    Berguna untuk frontend untuk mengetahui apakah user sudah login atau belum.
    """
    try:
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT id, username, role FROM users WHERE id = %s",
            (token["user_id"],)
        )
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
        
        return {
            "is_authenticated": True,
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking auth status: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking authentication status")
    finally:
        cursor.close()
        connection.close()

# 🔥 ENDPOINT TAMBAHAN UNTUK GET USER PUBLIC INFO
@router.get("/user/{user_id}/public")
def get_user_public_info(user_id: int):
    """
    Mendapatkan informasi public user.
    Bisa diakses tanpa autentikasi.
    """
    try:
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT id, username, nama_lengkap FROM users WHERE id = %s",
            (user_id,)
        )
        
        user = cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User tidak ditemukan")
        
        return {
            "id": user["id"],
            "username": user["username"],
            "nama_lengkap": user["nama_lengkap"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user public info: {str(e)}")
        raise HTTPException(status_code=500, detail="Error mengambil data user")
    finally:
        cursor.close()
        connection.close()