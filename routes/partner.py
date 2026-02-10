from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime
import logging
import json
import os
import uuid
from typing import Optional, List
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Partner"])

# ✅ PERBAIKI PATH UNTUK STATIC FILES
# Gunakan path relatif ke root project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTNER_IMAGE_DIR = os.path.join("static", "uploads", "partner")
FULL_PARTNER_DIR = os.path.join(BASE_DIR, "static", "uploads", "partner")

# Pastikan direktori ada
os.makedirs(FULL_PARTNER_DIR, exist_ok=True)
logger.info(f"Partner image directory: {FULL_PARTNER_DIR}")
logger.info(f"Directory exists: {os.path.exists(FULL_PARTNER_DIR)}")
logger.info(f"Directory writable: {os.access(FULL_PARTNER_DIR, os.W_OK)}")

# ✅ FUNGSI: Buat tabel partner jika belum ada
def create_partner_table():
    """Buat tabel partner jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS partner (
                id INT AUTO_INCREMENT PRIMARY KEY,
                section VARCHAR(100) NOT NULL,
                section_key VARCHAR(100) NOT NULL,
                content_type VARCHAR(20) NOT NULL,
                content_value LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_section_key (section, section_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        connection.commit()
        logger.info("✅ partner table ready")
    except Exception as e:
        logger.error(f"Error creating partner table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ENDPOINT UNTUK PARTNER (CRUD)
# ============================================

@router.get("/admin/partner")
def get_partner_content(token: dict = Depends(verify_token)):
    """Get semua konten Partner (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_partner_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM partner ORDER BY section, section_key")
        rows = cursor.fetchall()
        
        # Format data untuk frontend
        result = {}
        for row in rows:
            section = row['section']
            key = row['section_key']
            content_type = row['content_type']
            content_value = row['content_value']
            
            if section not in result:
                result[section] = {}
            
            # Parse content berdasarkan type
            if content_type == 'array' or content_type == 'object':
                try:
                    result[section][key] = json.loads(content_value) if content_value else []
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {section}.{key}: {e}")
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', 'Partner & Sponsorship'),
            "hero_subtitle": result.get('hero', {}).get('subtitle', 'Berkolaborasi untuk Kesuksesan Bersama'),
            "partners": result.get('partners', {}).get('items', [])
        }
        
        # Debug log
        logger.info(f"Found {len(rows)} rows in partner table")
        logger.info(f"Found {len(formatted_result['partners'])} partners")
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting Partner content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil konten Partner: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/partner")
async def update_partner_content(
    request: dict,
    token: dict = Depends(verify_token)
):
    """Update konten Partner (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    section = request.get('section')
    data = request.get('data', {})
    
    if not section:
        raise HTTPException(status_code=400, detail="Section harus diisi")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_partner_table()
        
        # Mapping untuk setiap section yang bisa diupdate
        section_mapping = {
            'hero': [
                ('title', 'text', data.get('hero_title', 'Partner & Sponsorship')),
                ('subtitle', 'text', data.get('hero_subtitle', 'Berkolaborasi untuk Kesuksesan Bersama'))
            ],
            'partners': [
                ('items', 'array', json.dumps(data.get('partners', [])))
            ]
        }
        
        # Update data untuk section yang diminta
        if section in section_mapping:
            for key, content_type, content_value in section_mapping[section]:
                # Check if record exists
                cursor.execute("""
                    SELECT id FROM partner 
                    WHERE section = %s AND section_key = %s
                """, (section, key))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing
                    cursor.execute("""
                        UPDATE partner 
                        SET content_type = %s, content_value = %s, updated_at = %s
                        WHERE section = %s AND section_key = %s
                    """, (content_type, content_value, datetime.now(), section, key))
                else:
                    # Insert new
                    cursor.execute("""
                        INSERT INTO partner (section, section_key, content_type, content_value)
                        VALUES (%s, %s, %s, %s)
                    """, (section, key, content_type, content_value))
        
        connection.commit()
        
        return {
            "message": f"Data {section} berhasil diupdate",
            "section": section,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating Partner content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate konten Partner: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/partner/reset")
def reset_partner_content(
    section: Optional[str] = None,
    token: dict = Depends(verify_token)
):
    """Reset konten Partner ke default (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_partner_table()
        
        if section:
            # Reset specific section
            cursor.execute("DELETE FROM partner WHERE section = %s", (section,))
            message = f"Data {section} berhasil direset ke default"
        else:
            # Reset all
            cursor.execute("DELETE FROM partner")
            message = "Semua data partner berhasil direset ke default"
        
        connection.commit()
        
        return {
            "message": message,
            "reset_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting Partner content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mereset konten Partner: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/partner/public")
def get_public_partner():
    """Get konten Partner untuk public (tanpa auth)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_partner_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM partner ORDER BY section, section_key")
        rows = cursor.fetchall()
        
        # Format data untuk frontend
        result = {}
        for row in rows:
            section = row['section']
            key = row['section_key']
            content_type = row['content_type']
            content_value = row['content_value']
            
            if section not in result:
                result[section] = {}
            
            # Parse content berdasarkan type
            if content_type == 'array' or content_type == 'object':
                try:
                    parsed_value = json.loads(content_value) if content_value else []
                    result[section][key] = parsed_value
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {section}.{key}: {e}")
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', 'Partner & Sponsorship'),
            "hero_subtitle": result.get('hero', {}).get('subtitle', 'Berkolaborasi untuk Kesuksesan Bersama'),
            "partners": result.get('partners', {}).get('items', [])
        }
        
        # Clean up logo URLs - tambahkan base URL jika hanya path relatif
        for partner in formatted_result["partners"]:
            if partner.get("logo"):
                if not partner["logo"].startswith(('http://', 'https://', '/')):
                    # Jika hanya filename, tambahkan path lengkap
                    partner["logo"] = f"/static/uploads/partner/{partner['logo']}"
                elif partner["logo"].startswith('/static/uploads/partner/'):
                    # Sudah benar
                    pass
                elif partner["logo"].startswith('static/uploads/partner/'):
                    # Tambahkan slash di depan
                    partner["logo"] = f"/{partner['logo']}"
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting public Partner: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data Partner: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ENDPOINT UNTUK UPLOAD GAMBAR PARTNER - DIPERBAIKI
# ============================================

@router.post("/admin/partner/upload-image")
async def upload_partner_image(
    image: UploadFile = File(...),
    partner_index: Optional[str] = Form(None),
    token: dict = Depends(verify_token)
):
    """Upload gambar untuk partner (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi file
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File harus berupa gambar")
    
    # Validasi ukuran file (max 5MB)
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    
    try:
        # Baca konten file
        contents = await image.read()
        file_size = len(contents)
        
        if file_size > MAX_SIZE:
            raise HTTPException(status_code=400, detail="Ukuran file maksimal 5MB")
        
        # Generate nama file unik
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Dapatkan ekstensi file
        file_extension = image.filename.split('.')[-1] if '.' in image.filename else 'jpg'
        valid_extensions = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']
        
        if file_extension.lower() not in valid_extensions:
            file_extension = 'jpg'
        
        filename = f"partner_{timestamp}_{unique_id}.{file_extension}"
        file_path = os.path.join(FULL_PARTNER_DIR, filename)
        
        # Simpan file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Generate URL untuk akses file
        image_url = f"/static/uploads/partner/{filename}"
        
        logger.info(f"✅ Partner image uploaded: {filename} ({file_size} bytes)")
        logger.info(f"   Path: {file_path}")
        logger.info(f"   URL: {image_url}")
        logger.info(f"   File exists: {os.path.exists(file_path)}")
        
        return {
            "message": "Gambar berhasil diupload",
            "image_url": image_url,
            "filename": filename,
            "file_size": file_size,
            "partner_index": partner_index,
            "full_path": file_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error uploading partner image: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error upload gambar: {str(e)}")

@router.get("/admin/partner/debug-upload")
def debug_upload_folder(token: dict = Depends(verify_token)):
    """Debug endpoint untuk mengecek folder upload"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    try:
        files = []
        if os.path.exists(FULL_PARTNER_DIR):
            for filename in os.listdir(FULL_PARTNER_DIR):
                file_path = os.path.join(FULL_PARTNER_DIR, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    files.append({
                        "filename": filename,
                        "size": file_size,
                        "path": file_path,
                        "url": f"/static/uploads/partner/{filename}",
                        "exists": os.path.exists(file_path)
                    })
        
        return {
            "directory": FULL_PARTNER_DIR,
            "exists": os.path.exists(FULL_PARTNER_DIR),
            "writable": os.access(FULL_PARTNER_DIR, os.W_OK),
            "file_count": len(files),
            "files": files
        }
    except Exception as e:
        logger.error(f"Error checking upload folder: {str(e)}")
        return {"error": str(e)}

# ============================================
# DATA DEFAULT UNTUK PARTNER - DIPERBAIKI
# ============================================

def initialize_default_partner_data():
    """Inisialisasi data default untuk partner jika tabel kosong"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah data sudah ada
        cursor.execute("SELECT COUNT(*) as count FROM partner")
        count = cursor.fetchone()['count']
        
        if count == 0:
            logger.info("📝 Initializing default partner data...")
            
            # Data hero default
            default_data = [
                ('hero', 'title', 'text', 'Partner & Sponsorship'),
                ('hero', 'subtitle', 'text', 'Berkolaborasi untuk Kesuksesan Bersama'),
                ('partners', 'items', 'array', json.dumps([
                    {
                        "name": "Nike",
                        "description": "Official Running Partner",
                        "category": "sponsor",
                        "logo": "",
                        "website": "https://nike.com",
                        "order": 1
                    },
                    {
                        "name": "Adidas",
                        "description": "Sports Equipment Partner",
                        "category": "sponsor",
                        "logo": "",
                        "website": "https://adidas.com",
                        "order": 2
                    },
                    {
                        "name": "Garmin",
                        "description": "Wearable Technology Partner",
                        "category": "sponsor",
                        "logo": "",
                        "website": "https://garmin.com",
                        "order": 3
                    },
                    {
                        "name": "Compressport",
                        "description": "Compression Wear Partner",
                        "category": "sponsor",
                        "logo": "",
                        "website": "https://compressport.com",
                        "order": 4
                    },
                    {
                        "name": "Runner's World",
                        "description": "Running Magazine Media Partner",
                        "category": "media",
                        "logo": "",
                        "website": "https://runnersworld.com",
                        "order": 5
                    },
                    {
                        "name": "Jogja Running Club",
                        "description": "Community Running Partner",
                        "category": "community",
                        "logo": "",
                        "website": "https://jogjarunningclub.com",
                        "order": 6
                    }
                ]))
            ]
            
            # Insert data default
            for section, key, content_type, content_value in default_data:
                cursor.execute("""
                    INSERT INTO partner (section, section_key, content_type, content_value)
                    VALUES (%s, %s, %s, %s)
                """, (section, key, content_type, content_value))
            
            connection.commit()
            logger.info("✅ Default partner data initialized")
        else:
            logger.info(f"✅ Partner table already has {count} rows")
            
    except Exception as e:
        logger.error(f"Error initializing default partner data: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        cursor.close()
        connection.close()

# Panggil fungsi inisialisasi saat module di-load
initialize_default_partner_data()