from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
import json
from typing import Optional
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Tentang Kami"])

# ✅ FUNGSI: Buat tabel tentang_kami jika belum ada
def create_tentang_kami_table():
    """Buat tabel tentang_kami jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami (
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
        logger.info("✅ tentang_kami table ready")
    except Exception as e:
        logger.error(f"Error creating tentang_kami table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ENDPOINT UNTUK TENTANG KAMI (CRUD) - MENGGUNAKAN DATABASE
# ============================================

@router.get("/admin/tentang-kami")
def get_tentang_kami_content(token: dict = Depends(verify_token)):
    """Get semua konten Tentang Kami (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_tentang_kami_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM tentang_kami ORDER BY section, section_key")
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
                    result[section][key] = json.loads(content_value)
                except:
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend (TANPA visi, misi, dan tim)
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', ''),
            "hero_subtitle": result.get('hero', {}).get('subtitle', ''),
            "hero_description": result.get('hero', {}).get('description', ''),
            "layanan": result.get('layanan', {}).get('items', []),
            "statistik": result.get('statistik', {}).get('items', []),
            "kontak_info": result.get('kontak', {}).get('info', {})
        }
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting Tentang Kami content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil konten Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/tentang-kami")
async def update_tentang_kami_content(
    request: dict,
    token: dict = Depends(verify_token)
):
    """Update konten Tentang Kami (admin only)"""
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
        create_tentang_kami_table()
        
        # Mapping untuk setiap section yang bisa diupdate
        section_mapping = {
            'hero': [
                ('title', 'text', data.get('hero_title', '')),
                ('subtitle', 'text', data.get('hero_subtitle', '')),
                ('description', 'text', data.get('hero_description', ''))
            ],
            'statistik': [
                ('items', 'array', json.dumps(data.get('statistik', [])))
            ],
            'layanan': [
                ('items', 'array', json.dumps(data.get('layanan', [])))
            ],
            'kontak': [
                ('info', 'object', json.dumps(data.get('kontak_info', {})))
            ]
        }
        
        # Update data untuk section yang diminta
        if section in section_mapping:
            for key, content_type, content_value in section_mapping[section]:
                # Check if record exists
                cursor.execute("""
                    SELECT id FROM tentang_kami 
                    WHERE section = %s AND section_key = %s
                """, (section, key))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing
                    cursor.execute("""
                        UPDATE tentang_kami 
                        SET content_type = %s, content_value = %s, updated_at = %s
                        WHERE section = %s AND section_key = %s
                    """, (content_type, content_value, datetime.now(), section, key))
                else:
                    # Insert new
                    cursor.execute("""
                        INSERT INTO tentang_kami (section, section_key, content_type, content_value)
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
        logger.error(f"Error updating Tentang Kami content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate konten Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/tentang-kami/reset")
def reset_tentang_kami_content(
    section: Optional[str] = None,
    token: dict = Depends(verify_token)
):
    """Reset konten Tentang Kami ke default (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_tentang_kami_table()
        
        if section:
            # Reset specific section
            cursor.execute("DELETE FROM tentang_kami WHERE section = %s", (section,))
            message = f"Data {section} berhasil direset ke default"
        else:
            # Reset all
            cursor.execute("DELETE FROM tentang_kami")
            message = "Semua data berhasil direset ke default"
        
        connection.commit()
        
        return {
            "message": message,
            "reset_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting Tentang Kami content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mereset konten Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/tentang-kami/public")
def get_public_tentang_kami():
    """Get konten Tentang Kami untuk public (tanpa auth)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_tentang_kami_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM tentang_kami ORDER BY section, section_key")
        rows = cursor.fetchall()
        
        # DEBUG: Log data yang diambil
        logger.info(f"DEBUG: Found {len(rows)} rows in tentang_kami table")
        for row in rows:
            logger.info(f"DEBUG: Section: {row['section']}, Key: {row['section_key']}, Type: {row['content_type']}")
        
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
                    logger.info(f"DEBUG: Parsed {section}.{key} as {type(parsed_value)}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {section}.{key}: {e}")
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend (TANPA visi, misi, dan tim)
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', ''),
            "hero_subtitle": result.get('hero', {}).get('subtitle', ''),
            "hero_description": result.get('hero', {}).get('description', ''),
            "layanan": result.get('layanan', {}).get('items', []),
            "statistik": result.get('statistik', {}).get('items', []),
            "kontak_info": result.get('kontak', {}).get('info', {})
        }
        
        # DEBUG: Log hasil akhir
        logger.info(f"DEBUG: Returning formatted result")
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting public Tentang Kami: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()