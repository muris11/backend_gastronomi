from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Footer Kontak"])

# ============================================
# ✅ FUNGSI: Buat tabel footer_kontak jika belum ada
# ============================================

def create_footer_kontak_table():
    """Buat tabel footer_kontak jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS footer_kontak (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL DEFAULT 'info@gastronomirun.com',
                phone VARCHAR(100) NOT NULL DEFAULT '(021) 1234-5678',
                address TEXT NOT NULL,
                description TEXT,
                copyright_text VARCHAR(255) NOT NULL DEFAULT '© 2024 Gastronomi Run. All rights reserved.',
                social_facebook VARCHAR(255),
                social_instagram VARCHAR(255),
                social_twitter VARCHAR(255),
                social_youtube VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        connection.commit()
        logger.info("✅ footer_kontak table ready")
        
        # Insert default data jika tabel masih kosong
        cursor.execute("SELECT COUNT(*) as count FROM footer_kontak")
        if cursor.fetchone()['count'] == 0:
            cursor.execute("""
                INSERT INTO footer_kontak (email, phone, address, description, copyright_text, 
                                          social_facebook, social_instagram, social_twitter, social_youtube)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                "info@gastronomirun.com",
                "(021) 1234-5678",
                "Jakarta Running Center, Indonesia",
                "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
                "© 2024 Gastronomi Run. All rights reserved.",
                "https://facebook.com/gastronomirun",
                "https://instagram.com/gastronomirun",
                "https://twitter.com/gastronomirun",
                "https://youtube.com/gastronomirun"
            ))
            connection.commit()
            logger.info("✅ Inserted default footer kontak data")
            
    except Exception as e:
        logger.error(f"Error creating footer_kontak table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK FOOTER KONTAK (GET)
# ============================================

@router.get("/admin/footer-kontak")
def get_footer_kontak(token: dict = Depends(verify_token)):
    """Get data footer kontak (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_footer_kontak_table()
        
        # Ambil data dari database
        cursor.execute("SELECT * FROM footer_kontak ORDER BY id DESC LIMIT 1")
        footer_data = cursor.fetchone()
        
        if not footer_data:
            # Return default data jika tidak ada
            default_data = {
                "email": "info@gastronomirun.com",
                "phone": "(021) 1234-5678",
                "address": "Jakarta Running Center, Indonesia",
                "description": "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
                "copyright": "© 2024 Gastronomi Run. All rights reserved.",
                "social_media": {
                    "facebook": "https://facebook.com/gastronomirun",
                    "instagram": "https://instagram.com/gastronomirun",
                    "twitter": "https://twitter.com/gastronomirun",
                    "youtube": "https://youtube.com/gastronomirun"
                }
            }
            return default_data
        
        # Format data sesuai yang diharapkan frontend
        formatted_data = {
            "email": footer_data['email'],
            "phone": footer_data['phone'],
            "address": footer_data['address'],
            "description": footer_data['description'] or "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
            "copyright": footer_data['copyright_text'] or "© 2024 Gastronomi Run. All rights reserved.",
            "social_media": {
                "facebook": footer_data['social_facebook'] or "",
                "instagram": footer_data['social_instagram'] or "",
                "twitter": footer_data['social_twitter'] or "",
                "youtube": footer_data['social_youtube'] or ""
            }
        }
        
        return formatted_data
        
    except Exception as e:
        logger.error(f"Error getting footer kontak data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data footer kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK FOOTER KONTAK (PUT/UPDATE)
# ============================================

@router.put("/admin/footer-kontak")
def update_footer_kontak(
    request: dict,
    token: dict = Depends(verify_token)
):
    """Update data footer kontak (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi input
    email = request.get('email', '').strip()
    phone = request.get('phone', '').strip()
    address = request.get('address', '').strip()
    copyright_text = request.get('copyright', '').strip()
    description = request.get('description', '').strip()
    social_media = request.get('social_media', {})
    
    # Validasi required fields
    if not email:
        raise HTTPException(status_code=400, detail="Email harus diisi")
    if not phone:
        raise HTTPException(status_code=400, detail="Telepon harus diisi")
    if not address:
        raise HTTPException(status_code=400, detail="Alamat harus diisi")
    if not copyright_text:
        raise HTTPException(status_code=400, detail="Copyright text harus diisi")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_footer_kontak_table()
        
        # Ambil data existing untuk cek apakah ada data
        cursor.execute("SELECT id FROM footer_kontak ORDER BY id DESC LIMIT 1")
        existing_data = cursor.fetchone()
        
        if existing_data:
            # Update data existing
            cursor.execute("""
                UPDATE footer_kontak 
                SET email = %s, phone = %s, address = %s, description = %s, 
                    copyright_text = %s, social_facebook = %s, social_instagram = %s, 
                    social_twitter = %s, social_youtube = %s, updated_at = %s
                WHERE id = %s
            """, (
                email,
                phone,
                address,
                description,
                copyright_text,
                social_media.get('facebook', ''),
                social_media.get('instagram', ''),
                social_media.get('twitter', ''),
                social_media.get('youtube', ''),
                datetime.now(),
                existing_data['id']
            ))
            message = "Data footer kontak berhasil diperbarui"
        else:
            # Insert data baru
            cursor.execute("""
                INSERT INTO footer_kontak 
                (email, phone, address, description, copyright_text, 
                 social_facebook, social_instagram, social_twitter, social_youtube)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                email,
                phone,
                address,
                description,
                copyright_text,
                social_media.get('facebook', ''),
                social_media.get('instagram', ''),
                social_media.get('twitter', ''),
                social_media.get('youtube', '')
            ))
            message = "Data footer kontak berhasil disimpan"
        
        connection.commit()
        
        # Ambil data yang baru saja disimpan untuk response
        cursor.execute("SELECT * FROM footer_kontak ORDER BY id DESC LIMIT 1")
        updated_data = cursor.fetchone()
        
        formatted_data = {
            "email": updated_data['email'],
            "phone": updated_data['phone'],
            "address": updated_data['address'],
            "description": updated_data['description'],
            "copyright": updated_data['copyright_text'],
            "social_media": {
                "facebook": updated_data['social_facebook'] or "",
                "instagram": updated_data['social_instagram'] or "",
                "twitter": updated_data['social_twitter'] or "",
                "youtube": updated_data['social_youtube'] or ""
            }
        }
        
        return {
            "message": message,
            "data": formatted_data,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating footer kontak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan data footer kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK FOOTER KONTAK PUBLIC (GET)
# ============================================

@router.get("/footer-kontak/public")
def get_public_footer_kontak():
    """Get data footer kontak untuk public (tanpa auth)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_footer_kontak_table()
        
        # Ambil data dari database
        cursor.execute("SELECT * FROM footer_kontak ORDER BY id DESC LIMIT 1")
        footer_data = cursor.fetchone()
        
        if not footer_data:
            # Return default data jika tidak ada
            default_data = {
                "email": "info@gastronomirun.com",
                "phone": "(021) 1234-5678",
                "address": "Jakarta Running Center, Indonesia",
                "description": "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
                "copyright": "© 2024 Gastronomi Run. All rights reserved.",
                "social_media": {
                    "facebook": "https://facebook.com/gastronomirun",
                    "instagram": "https://instagram.com/gastronomirun",
                    "twitter": "https://twitter.com/gastronomirun",
                    "youtube": "https://youtube.com/gastronomirun"
                }
            }
            return default_data
        
        # Format data sesuai yang diharapkan frontend
        formatted_data = {
            "email": footer_data['email'],
            "phone": footer_data['phone'],
            "address": footer_data['address'],
            "description": footer_data['description'] or "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
            "copyright": footer_data['copyright_text'] or "© 2024 Gastronomi Run. All rights reserved.",
            "social_media": {
                "facebook": footer_data['social_facebook'] or "",
                "instagram": footer_data['social_instagram'] or "",
                "twitter": footer_data['social_twitter'] or "",
                "youtube": footer_data['social_youtube'] or ""
            }
        }
        
        return formatted_data
        
    except Exception as e:
        logger.error(f"Error getting public footer kontak data: {str(e)}")
        # Return default data jika error
        return {
            "email": "info@gastronomirun.com",
            "phone": "(021) 1234-5678",
            "address": "Jakarta Running Center, Indonesia",
            "description": "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
            "copyright": "© 2024 Gastronomi Run. All rights reserved.",
            "social_media": {
                "facebook": "https://facebook.com/gastronomirun",
                "instagram": "https://instagram.com/gastronomirun",
                "twitter": "https://twitter.com/gastronomirun",
                "youtube": "https://youtube.com/gastronomirun"
            }
        }
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK RESET FOOTER KONTAK
# ============================================

@router.delete("/admin/footer-kontak/reset")
def reset_footer_kontak(token: dict = Depends(verify_token)):
    """Reset data footer kontak ke default (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_footer_kontak_table()
        
        # Hapus semua data
        cursor.execute("DELETE FROM footer_kontak")
        
        # Insert default data
        cursor.execute("""
            INSERT INTO footer_kontak (email, phone, address, description, copyright_text, 
                                      social_facebook, social_instagram, social_twitter, social_youtube)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "info@gastronomirun.com",
            "(021) 1234-5678",
            "Jakarta Running Center, Indonesia",
            "Gastronomi Run adalah bagian dari komitmen untuk merealisasikan kemajuan urban dan industri olahraga di Indonesia. Kami menyediakan layanan yang terbaik dan inovatif untuk semua orang.",
            "© 2024 Gastronomi Run. All rights reserved.",
            "https://facebook.com/gastronomirun",
            "https://instagram.com/gastronomirun",
            "https://twitter.com/gastronomirun",
            "https://youtube.com/gastronomirun"
        ))
        
        connection.commit()
        
        return {
            "message": "Data footer kontak berhasil direset ke default",
            "reset_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting footer kontak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mereset data footer kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK FOOTER KONTAK STATISTIK
# ============================================

@router.get("/admin/footer-kontak/stats")
def get_footer_kontak_stats(token: dict = Depends(verify_token)):
    """Get statistik data footer kontak (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_footer_kontak_table()
        
        # Ambil data statistik
        cursor.execute("SELECT COUNT(*) as total_entries FROM footer_kontak")
        total_entries = cursor.fetchone()['total_entries']
        
        cursor.execute("SELECT MAX(updated_at) as last_updated FROM footer_kontak")
        last_updated = cursor.fetchone()['last_updated']
        
        cursor.execute("SELECT * FROM footer_kontak ORDER BY id DESC LIMIT 1")
        current_data = cursor.fetchone()
        
        stats = {
            "total_entries": total_entries,
            "last_updated": last_updated,
            "has_data": current_data is not None,
            "current_data_summary": {
                "has_email": bool(current_data and current_data['email']),
                "has_phone": bool(current_data and current_data['phone']),
                "has_address": bool(current_data and current_data['address']),
                "has_description": bool(current_data and current_data['description']),
                "has_copyright": bool(current_data and current_data['copyright_text']),
                "social_media_count": sum([
                    1 if current_data and current_data['social_facebook'] else 0,
                    1 if current_data and current_data['social_instagram'] else 0,
                    1 if current_data and current_data['social_twitter'] else 0,
                    1 if current_data and current_data['social_youtube'] else 0
                ]) if current_data else 0
            }
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting footer kontak stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil statistik footer kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# NOTE:
# Hindari inisialisasi database saat module import di shared hosting.
# Buat tabel lewat migrasi/deploy step atau endpoint admin terkontrol.
