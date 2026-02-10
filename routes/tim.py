# app/routes/admin/tim.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime
import logging
import os
import shutil
import json
from PIL import Image
from typing import Optional
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Tim"])

# Path untuk menyimpan file upload
TIM_UPLOAD_DIR = "uploads/tim"
os.makedirs(TIM_UPLOAD_DIR, exist_ok=True)

# Konfigurasi gambar tim
TIM_TARGET_WIDTH = 400
TIM_TARGET_HEIGHT = 400

# ============================================
# ✅ FUNGSI: Proses gambar tim
# ============================================

def process_tim_image(file_path: str) -> dict:
    """Proses gambar tim menjadi persegi 400x400"""
    try:
        with Image.open(file_path) as img:
            # Get original dimensions
            original_width, original_height = img.size
            
            # Convert ke RGB jika perlu
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate cropping untuk buat persegi
            if original_width > original_height:
                # Landscape: crop width
                left = (original_width - original_height) // 2
                top = 0
                right = left + original_height
                bottom = original_height
            else:
                # Portrait: crop height
                left = 0
                top = (original_height - original_width) // 2
                right = original_width
                bottom = top + original_width
            
            # Crop gambar menjadi persegi
            img_cropped = img.crop((left, top, right, bottom))
            
            # Resize ke 400x400
            img_resized = img_cropped.resize((TIM_TARGET_WIDTH, TIM_TARGET_HEIGHT), Image.Resampling.LANCZOS)
            img_resized.save(file_path, quality=90, optimize=True)
            
            return {
                "success": True,
                "action": "cropped_and_resized",
                "original_size": (original_width, original_height),
                "crop_area": (left, top, right, bottom),
                "new_size": (TIM_TARGET_WIDTH, TIM_TARGET_HEIGHT)
            }
            
    except Exception as e:
        logger.error(f"Error processing tim image: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================
# ✅ FUNGSI UNTUK MENGELOLA TABEL TIM
# ============================================

def create_tim_tables():
    """Buat tabel untuk tim jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Tabel anggota tim
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami_tim (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nama VARCHAR(100) NOT NULL,
                jabatan VARCHAR(100) NOT NULL,
                deskripsi TEXT,
                foto VARCHAR(255),
                urutan INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_urutan (urutan),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Tabel keahlian (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami_tim_keahlian (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tim_id INT NOT NULL,
                keahlian VARCHAR(100) NOT NULL,
                urutan INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tim_id) REFERENCES tentang_kami_tim(id) ON DELETE CASCADE,
                INDEX idx_tim_id (tim_id),
                INDEX idx_urutan (urutan)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        connection.commit()
        logger.info("✅ Tabel tentang_kami_tim dan tentang_kami_tim_keahlian siap")
        
    except Exception as e:
        logger.error(f"Error creating tim tables: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK MANAJEMEN TIM (DATABASE)
# ============================================

@router.get("/admin/tim")
def get_all_tim_members(token: dict = Depends(verify_token)):
    """Get semua anggota tim (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_tim_tables()  # Pastikan tabel ada
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil semua anggota tim
        cursor.execute("""
            SELECT * FROM tentang_kami_tim 
            ORDER BY urutan ASC, created_at DESC
        """)
        
        members = cursor.fetchall()
        
        # Untuk setiap anggota, ambil keahliannya
        for member in members:
            cursor.execute("""
                SELECT keahlian FROM tentang_kami_tim_keahlian 
                WHERE tim_id = %s 
                ORDER BY urutan ASC
            """, (member['id'],))
            
            keahlian_rows = cursor.fetchall()
            member['keahlian'] = [row['keahlian'] for row in keahlian_rows]
            
            # Tambahkan URL foto jika ada
            if member['foto']:
                member['foto_url'] = f"http://localhost:8000/uploads/tim/{member['foto']}"
            else:
                member['foto_url'] = None
        
        return members
        
    except Exception as e:
        logger.error(f"Error getting tim members: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data tim: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/tim/public")
def get_public_tim_members():
    """Get anggota tim untuk public (tanpa auth)"""
    create_tim_tables()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil hanya anggota yang aktif
        cursor.execute("""
            SELECT * FROM tentang_kami_tim 
            WHERE is_active = TRUE 
            ORDER BY urutan ASC, created_at DESC
        """)
        
        members = cursor.fetchall()
        
        # Untuk setiap anggota, ambil keahliannya
        for member in members:
            cursor.execute("""
                SELECT keahlian FROM tentang_kami_tim_keahlian 
                WHERE tim_id = %s 
                ORDER BY urutan ASC
            """, (member['id'],))
            
            keahlian_rows = cursor.fetchall()
            member['keahlian'] = [row['keahlian'] for row in keahlian_rows]
            
            # Tambahkan URL foto jika ada
            if member['foto']:
                member['foto_url'] = f"http://localhost:8000/uploads/tim/{member['foto']}"
            else:
                member['foto_url'] = None
        
        return members
        
    except Exception as e:
        logger.error(f"Error getting public tim members: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data tim: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/admin/tim")
async def create_tim_member(
    nama: str = Form(...),
    jabatan: str = Form(...),
    deskripsi: str = Form(None),
    urutan: int = Form(0),
    is_active: bool = Form(True),
    keahlian: str = Form("[]"),  # JSON array of strings
    token: dict = Depends(verify_token)
):
    """Tambah anggota tim baru (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_tim_tables()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Insert anggota tim
        cursor.execute("""
            INSERT INTO tentang_kami_tim 
            (nama, jabatan, deskripsi, urutan, is_active)
            VALUES (%s, %s, %s, %s, %s)
        """, (nama, jabatan, deskripsi, urutan, is_active))
        
        tim_id = cursor.lastrowid
        
        # Parse dan insert keahlian
        try:
            keahlian_list = json.loads(keahlian)
            for idx, skill in enumerate(keahlian_list):
                cursor.execute("""
                    INSERT INTO tentang_kami_tim_keahlian (tim_id, keahlian, urutan)
                    VALUES (%s, %s, %s)
                """, (tim_id, skill, idx))
        except json.JSONDecodeError:
            logger.warning(f"Invalid keahlian JSON for tim_id {tim_id}")
        
        connection.commit()
        
        # Ambil data yang baru dibuat
        cursor.execute("SELECT * FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        member = cursor.fetchone()
        
        # Ambil keahlian
        cursor.execute("""
            SELECT keahlian FROM tentang_kami_tim_keahlian 
            WHERE tim_id = %s ORDER BY urutan ASC
        """, (tim_id,))
        keahlian_rows = cursor.fetchall()
        member['keahlian'] = [row['keahlian'] for row in keahlian_rows]
        
        if member['foto']:
            member['foto_url'] = f"http://localhost:8000/uploads/tim/{member['foto']}"
        
        return {
            "message": "Anggota tim berhasil ditambahkan",
            "tim_id": tim_id,
            "member": member
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error creating tim member: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menambah anggota tim: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/tim/{tim_id}")
async def update_tim_member(
    tim_id: int,
    nama: str = Form(None),
    jabatan: str = Form(None),
    deskripsi: str = Form(None),
    urutan: int = Form(None),
    is_active: bool = Form(None),
    keahlian: str = Form(None),  # JSON array of strings
    token: dict = Depends(verify_token)
):
    """Update anggota tim (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah anggota ada
        cursor.execute("SELECT id FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Anggota tim tidak ditemukan")
        
        # Update data anggota
        update_fields = []
        update_values = []
        
        if nama is not None:
            update_fields.append("nama = %s")
            update_values.append(nama)
        
        if jabatan is not None:
            update_fields.append("jabatan = %s")
            update_values.append(jabatan)
        
        if deskripsi is not None:
            update_fields.append("deskripsi = %s")
            update_values.append(deskripsi)
        
        if urutan is not None:
            update_fields.append("urutan = %s")
            update_values.append(urutan)
        
        if is_active is not None:
            update_fields.append("is_active = %s")
            update_values.append(is_active)
        
        update_fields.append("updated_at = %s")
        update_values.append(datetime.now())
        
        if update_fields:
            update_values.append(tim_id)
            update_query = f"""
                UPDATE tentang_kami_tim 
                SET {', '.join(update_fields)} 
                WHERE id = %s
            """
            cursor.execute(update_query, update_values)
        
        # Update keahlian jika diberikan
        if keahlian is not None:
            try:
                # Hapus keahlian lama
                cursor.execute("DELETE FROM tentang_kami_tim_keahlian WHERE tim_id = %s", (tim_id,))
                
                # Insert keahlian baru
                keahlian_list = json.loads(keahlian)
                for idx, skill in enumerate(keahlian_list):
                    cursor.execute("""
                        INSERT INTO tentang_kami_tim_keahlian (tim_id, keahlian, urutan)
                        VALUES (%s, %s, %s)
                    """, (tim_id, skill, idx))
            except json.JSONDecodeError:
                logger.warning(f"Invalid keahlian JSON for tim_id {tim_id}")
        
        connection.commit()
        
        # Ambil data terbaru
        cursor.execute("SELECT * FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        member = cursor.fetchone()
        
        cursor.execute("""
            SELECT keahlian FROM tentang_kami_tim_keahlian 
            WHERE tim_id = %s ORDER BY urutan ASC
        """, (tim_id,))
        keahlian_rows = cursor.fetchall()
        member['keahlian'] = [row['keahlian'] for row in keahlian_rows]
        
        if member['foto']:
            member['foto_url'] = f"http://localhost:8000/uploads/tim/{member['foto']}"
        
        return {
            "message": "Anggota tim berhasil diupdate",
            "tim_id": tim_id,
            "member": member
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating tim member: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate anggota tim: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/tim/{tim_id}")
def delete_tim_member(
    tim_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus anggota tim (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil info foto untuk dihapus
        cursor.execute("SELECT foto FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Anggota tim tidak ditemukan")
        
        # Hapus foto dari sistem jika ada
        if member['foto']:
            file_path = os.path.join(TIM_UPLOAD_DIR, member['foto'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Error deleting file: {str(e)}")
        
        # Hapus dari database (CASCADE akan menghapus keahlian juga)
        cursor.execute("DELETE FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        connection.commit()
        
        return {
            "message": "Anggota tim berhasil dihapus",
            "tim_id": tim_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting tim member: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus anggota tim: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK UPLOAD FOTO TIM
# ============================================

@router.post("/admin/tim/{tim_id}/upload-foto")
async def upload_tim_foto(
    tim_id: int,
    file: UploadFile = File(...),
    token: dict = Depends(verify_token)
):
    """Upload foto untuk anggota tim (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi file
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File harus berupa gambar")
    
    # Validasi ukuran file (max 5MB)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 5MB")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah anggota tim ada
        cursor.execute("SELECT id, foto FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Anggota tim tidak ditemukan")
        
        # Hapus foto lama jika ada
        if member['foto']:
            old_file_path = os.path.join(TIM_UPLOAD_DIR, member['foto'])
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception as e:
                    logger.warning(f"Error deleting old file: {str(e)}")
        
        # Generate nama file unik
        file_extension = file.filename.split('.')[-1]
        unique_filename = f"tim_{tim_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
        
        # Simpan file
        file_path = os.path.join(TIM_UPLOAD_DIR, unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Proses gambar tim
        process_result = process_tim_image(file_path)
        
        if not process_result.get('success', False):
            logger.warning(f"Image processing may have failed: {process_result}")
        
        # Update database dengan nama file baru
        cursor.execute("""
            UPDATE tentang_kami_tim 
            SET foto = %s, updated_at = %s 
            WHERE id = %s
        """, (unique_filename, datetime.now(), tim_id))
        
        connection.commit()
        
        foto_url = f"http://localhost:8000/uploads/tim/{unique_filename}"
        
        return {
            "message": "Foto berhasil diupload",
            "tim_id": tim_id,
            "filename": unique_filename,
            "foto_url": foto_url,
            "process_result": process_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Hapus file jika gagal
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        logger.error(f"Error uploading tim foto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupload foto: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/tim/{tim_id}/hapus-foto")
def delete_tim_foto(
    tim_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus foto anggota tim (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil info foto
        cursor.execute("SELECT foto FROM tentang_kami_tim WHERE id = %s", (tim_id,))
        member = cursor.fetchone()
        
        if not member:
            raise HTTPException(status_code=404, detail="Anggota tim tidak ditemukan")
        
        if not member['foto']:
            raise HTTPException(status_code=400, detail="Anggota tim tidak memiliki foto")
        
        # Hapus file dari sistem
        file_path = os.path.join(TIM_UPLOAD_DIR, member['foto'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Error deleting file: {str(e)}")
        
        # Update database
        cursor.execute("""
            UPDATE tentang_kami_tim 
            SET foto = NULL, updated_at = %s 
            WHERE id = %s
        """, (datetime.now(), tim_id))
        
        connection.commit()
        
        return {
            "message": "Foto berhasil dihapus",
            "tim_id": tim_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting tim foto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus foto: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ FUNGSI UNTUK MIGRASI DATA LAMA (OPSIONAL)
# ============================================

def migrate_old_tim_data():
    """Migrasi data tim dari JSON ke database (jalankan sekali)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah tabel tentang_kami ada
        cursor.execute("SHOW TABLES LIKE 'tentang_kami'")
        if not cursor.fetchone():
            logger.info("Tabel tentang_kami tidak ditemukan, skip migrasi")
            return
        
        # Cek apakah sudah ada data di tabel tim
        cursor.execute("SELECT COUNT(*) as count FROM tentang_kami_tim")
        if cursor.fetchone()['count'] > 0:
            logger.info("Data tim sudah ada, skip migrasi")
            return
        
        # Ambil data tim lama dari JSON
        cursor.execute("""
            SELECT content_value FROM tentang_kami 
            WHERE section = 'tim' AND section_key = 'members'
        """)
        
        old_data = cursor.fetchone()
        if not old_data or not old_data['content_value']:
            logger.info("Tidak ada data tim lama untuk dimigrasi")
            return
        
        try:
            members = json.loads(old_data['content_value'])
            logger.info(f"Found {len(members)} old tim members to migrate")
            
            for idx, member in enumerate(members):
                # Insert ke tabel baru
                cursor.execute("""
                    INSERT INTO tentang_kami_tim 
                    (nama, jabatan, deskripsi, urutan, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    member.get('name', ''),
                    member.get('position', ''),
                    member.get('description', ''),
                    idx,
                    True
                ))
                
                tim_id = cursor.lastrowid
                
                # Insert keahlian jika ada
                expertise = member.get('expertise', [])
                for skill_idx, skill in enumerate(expertise):
                    cursor.execute("""
                        INSERT INTO tentang_kami_tim_keahlian (tim_id, keahlian, urutan)
                        VALUES (%s, %s, %s)
                    """, (tim_id, skill, skill_idx))
            
            connection.commit()
            logger.info(f"✅ Successfully migrated {len(members)} tim members to database")
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing old tim data: {e}")
        except Exception as e:
            logger.error(f"Error during migration: {str(e)}")
            connection.rollback()
            
    except Exception as e:
        logger.error(f"Error migrating tim data: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Jalankan migrasi saat module di-load
migrate_old_tim_data()