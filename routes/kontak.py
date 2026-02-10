# app/routes/admin/kontak.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime
import logging
import os
import shutil
import json
from typing import Optional
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Kontak"])

# Path untuk menyimpan file upload
KONTAK_UPLOAD_DIR = "uploads/kontak"
os.makedirs(KONTAK_UPLOAD_DIR, exist_ok=True)

# ============================================
# ✅ FUNGSI: Buat semua tabel kontak jika belum ada
# ============================================

def create_contact_tables():
    """Buat semua tabel untuk kontak (tanpa JSON)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # 1. Buat tabel kontak (hero section) jika belum ada
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kontak (
                id INT AUTO_INCREMENT PRIMARY KEY,
                hero_title VARCHAR(200) NOT NULL,
                hero_subtitle VARCHAR(200) NOT NULL,
                hero_description TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Buat tabel contact_items jika belum ada
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                icon VARCHAR(50) NOT NULL,
                title VARCHAR(100) NOT NULL,
                action_url VARCHAR(500),
                order_position INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Buat tabel contact_details jika belum ada
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contact_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                contact_item_id INT NOT NULL,
                detail_text VARCHAR(255) NOT NULL,
                detail_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_contact_item_id (contact_item_id)
            )
        """)
        
        connection.commit()
        logger.info("✅ All contact tables created/checked")
        
        # 4. Insert data default jika tabel kontak kosong
        cursor.execute("SELECT COUNT(*) as count FROM kontak")
        kontak_count = cursor.fetchone()['count']
        
        if kontak_count == 0:
            cursor.execute("""
                INSERT INTO kontak (hero_title, hero_subtitle, hero_description)
                VALUES (%s, %s, %s)
            """, (
                "Hubungi Kami",
                "Kami Siap Membantu Anda",
                "Punya pertanyaan, saran, atau ingin berkolaborasi? Tim kami siap membantu Anda dengan solusi terbaik untuk kebutuhan event lari Anda."
            ))
            connection.commit()
            logger.info("✅ Inserted default kontak data")
        
        # 5. Insert data default untuk contact_items jika kosong
        cursor.execute("SELECT COUNT(*) as count FROM contact_items")
        contact_items_count = cursor.fetchone()['count']
        
        if contact_items_count == 0:
            default_contacts = [
                {
                    "icon": "Mail",
                    "title": "Email",
                    "action_url": "mailto:info@gastronomirun.com",
                    "order_position": 1,
                    "details": ["info@gastronomirun.com", "support@gastronomirun.com"]
                },
                {
                    "icon": "Phone",
                    "title": "Telepon",
                    "action_url": "tel:+622112345678",
                    "order_position": 2,
                    "details": ["(021) 1234-5678", "0812-3456-7890"]
                },
                {
                    "icon": "MapPin",
                    "title": "Alamat",
                    "action_url": "https://maps.google.com",
                    "order_position": 3,
                    "details": ["Jakarta Running Center", "Jl. Sudirman No. 123", "Jakarta Selatan, 12190"]
                },
                {
                    "icon": "Clock",
                    "title": "Jam Operasional",
                    "action_url": None,
                    "order_position": 4,
                    "details": ["Senin - Jumat: 08:00 - 17:00", "Sabtu: 08:00 - 12:00", "Minggu: Tutup"]
                }
            ]
            
            for contact in default_contacts:
                cursor.execute("""
                    INSERT INTO contact_items (icon, title, action_url, order_position, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    contact["icon"],
                    contact["title"],
                    contact["action_url"],
                    contact["order_position"],
                    True
                ))
                
                item_id = cursor.lastrowid
                
                # Insert details
                if contact["details"]:
                    for i, detail in enumerate(contact["details"]):
                        if detail and detail.strip():
                            cursor.execute("""
                                INSERT INTO contact_details (contact_item_id, detail_text, detail_order)
                                VALUES (%s, %s, %s)
                            """, (item_id, detail.strip(), i + 1))
            
            connection.commit()
            logger.info("✅ Inserted default contact items with details")
            
    except Exception as e:
        logger.error(f"Error creating contact tables: {str(e)}")
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK MANAJEMEN KONTAK (HERO SECTION)
# ============================================

@router.get("/admin/kontak")
def get_kontak_content(token: dict = Depends(verify_token)):
    """Get semua konten Kontak (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_contact_tables()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Set group_concat_max_len untuk menghindari truncation
        cursor.execute("SET SESSION group_concat_max_len = 1000000")
        
        # Ambil data hero section dari tabel kontak
        cursor.execute("SELECT * FROM kontak ORDER BY id DESC LIMIT 1")
        kontak_data = cursor.fetchone()
        
        if not kontak_data:
            # Insert data default jika tidak ada
            cursor.execute("""
                INSERT INTO kontak (hero_title, hero_subtitle, hero_description)
                VALUES (%s, %s, %s)
            """, (
                "Hubungi Kami",
                "Kami Siap Membantu Anda",
                "Punya pertanyaan, saran, atau ingin berkolaborasi? Tim kami siap membantu Anda dengan solusi terbaik untuk kebutuhan event lari Anda."
            ))
            connection.commit()
            cursor.execute("SELECT * FROM kontak ORDER BY id DESC LIMIT 1")
            kontak_data = cursor.fetchone()
        
        # Ambil semua contact items aktif dengan details
        cursor.execute("""
            SELECT ci.*, 
                   GROUP_CONCAT(cd.detail_text ORDER BY cd.detail_order SEPARATOR '|||') as details_text
            FROM contact_items ci
            LEFT JOIN contact_details cd ON ci.id = cd.contact_item_id
            WHERE ci.is_active = TRUE
            GROUP BY ci.id
            ORDER BY ci.order_position ASC, ci.created_at DESC
        """)
        
        contact_items = cursor.fetchall()
        
        # Format details menjadi list
        for item in contact_items:
            if item['details_text']:
                # Hapus None values dan split
                details_str = str(item['details_text']) if item['details_text'] else ''
                item['details'] = [d for d in details_str.split('|||') if d]
            else:
                item['details'] = []
            
            # Hapus field sementara
            if 'details_text' in item:
                del item['details_text']
        
        return {
            "hero_title": kontak_data.get('hero_title', ''),
            "hero_subtitle": kontak_data.get('hero_subtitle', ''),
            "hero_description": kontak_data.get('hero_description', ''),
            "contact_items": contact_items
        }
        
    except Exception as e:
        logger.error(f"Error getting kontak content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/kontak/hero")
async def update_kontak_hero(
    request: dict,
    token: dict = Depends(verify_token)
):
    """Update hero section kontak (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    hero_title = request.get('hero_title')
    hero_subtitle = request.get('hero_subtitle')
    hero_description = request.get('hero_description')
    
    if not all([hero_title, hero_subtitle, hero_description]):
        raise HTTPException(status_code=400, detail="Semua field hero section harus diisi")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek data existing
        cursor.execute("SELECT id FROM kontak ORDER BY id DESC LIMIT 1")
        existing_data = cursor.fetchone()
        
        if existing_data:
            # Update data existing
            cursor.execute("""
                UPDATE kontak 
                SET hero_title = %s, hero_subtitle = %s, hero_description = %s, updated_at = %s
                WHERE id = %s
            """, (
                hero_title,
                hero_subtitle,
                hero_description,
                datetime.now(),
                existing_data['id']
            ))
        else:
            # Insert data baru
            cursor.execute("""
                INSERT INTO kontak (hero_title, hero_subtitle, hero_description)
                VALUES (%s, %s, %s)
            """, (hero_title, hero_subtitle, hero_description))
        
        connection.commit()
        
        return {
            "message": "Hero section berhasil diupdate",
            "hero_title": hero_title,
            "hero_subtitle": hero_subtitle,
            "hero_description": hero_description,
            "updated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating kontak hero: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate hero section: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/admin/kontak/contact-items")
def get_all_contact_items(token: dict = Depends(verify_token)):
    """Get semua contact items (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_contact_tables()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Set group_concat_max_len untuk menghindari truncation
        cursor.execute("SET SESSION group_concat_max_len = 1000000")
        
        cursor.execute("""
            SELECT ci.*, 
                   GROUP_CONCAT(cd.detail_text ORDER BY cd.detail_order SEPARATOR '|||') as details_text
            FROM contact_items ci
            LEFT JOIN contact_details cd ON ci.id = cd.contact_item_id
            GROUP BY ci.id
            ORDER BY ci.order_position ASC, ci.created_at DESC
        """)
        
        contact_items = cursor.fetchall()
        
        # Format details menjadi list
        for item in contact_items:
            if item['details_text']:
                # Hapus None values dan split
                details_str = str(item['details_text']) if item['details_text'] else ''
                item['details'] = [d for d in details_str.split('|||') if d]
            else:
                item['details'] = []
            
            # Hapus field sementara
            if 'details_text' in item:
                del item['details_text']
        
        return contact_items
        
    except Exception as e:
        logger.error(f"Error getting contact items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data contact items: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/admin/kontak/contact-items")
async def create_contact_item(
    icon: str = Form(...),
    title: str = Form(...),
    details: str = Form("[]"),  # JSON array
    action_url: str = Form(None),
    order_position: int = Form(0),
    is_active: bool = Form(True),
    token: dict = Depends(verify_token)
):
    """Buat contact item baru (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_contact_tables()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Validasi details JSON
        try:
            details_list = json.loads(details)
            if not isinstance(details_list, list):
                raise ValueError("Details harus berupa array")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Format details tidak valid: {str(e)}")
        
        # Insert contact item
        cursor.execute("""
            INSERT INTO contact_items (icon, title, action_url, order_position, is_active)
            VALUES (%s, %s, %s, %s, %s)
        """, (icon, title, action_url, order_position, is_active))
        
        item_id = cursor.lastrowid
        connection.commit()
        
        # Insert details
        if details_list:
            for i, detail in enumerate(details_list):
                if detail and str(detail).strip():  # Hanya insert jika detail tidak kosong
                    cursor.execute("""
                        INSERT INTO contact_details (contact_item_id, detail_text, detail_order)
                        VALUES (%s, %s, %s)
                    """, (item_id, str(detail).strip(), i + 1))
        
        connection.commit()
        
        # Ambil data lengkap untuk response
        cursor.execute("SET SESSION group_concat_max_len = 1000000")
        cursor.execute("""
            SELECT ci.*, 
                   GROUP_CONCAT(cd.detail_text ORDER BY cd.detail_order SEPARATOR '|||') as details_text
            FROM contact_items ci
            LEFT JOIN contact_details cd ON ci.id = cd.contact_item_id
            WHERE ci.id = %s
            GROUP BY ci.id
        """, (item_id,))
        
        new_item = cursor.fetchone()
        
        # Format details
        if new_item['details_text']:
            details_str = str(new_item['details_text']) if new_item['details_text'] else ''
            new_item['details'] = [d for d in details_str.split('|||') if d]
        else:
            new_item['details'] = []
        
        # Hapus field sementara
        if 'details_text' in new_item:
            del new_item['details_text']
        
        return {
            "message": "Contact item berhasil dibuat",
            "contact_item": new_item
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error creating contact item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error membuat contact item: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/kontak/contact-items/{item_id}")
async def update_contact_item(
    item_id: int,
    icon: str = Form(None),
    title: str = Form(None),
    details: str = Form(None),
    action_url: str = Form(None),
    order_position: int = Form(None),
    is_active: bool = Form(None),
    token: dict = Depends(verify_token)
):
    """Update contact item (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah item ada
        cursor.execute("SELECT id FROM contact_items WHERE id = %s", (item_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Contact item tidak ditemukan")
        
        # Update data contact item
        update_fields = []
        update_values = []
        
        if icon is not None:
            update_fields.append("icon = %s")
            update_values.append(icon)
        
        if title is not None:
            update_fields.append("title = %s")
            update_values.append(title)
        
        if action_url is not None:
            update_fields.append("action_url = %s")
            update_values.append(action_url)
        
        if order_position is not None:
            update_fields.append("order_position = %s")
            update_values.append(order_position)
        
        if is_active is not None:
            update_fields.append("is_active = %s")
            update_values.append(is_active)
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            update_values.append(item_id)
            update_query = f"""
                UPDATE contact_items 
                SET {', '.join(update_fields)} 
                WHERE id = %s
            """
            cursor.execute(update_query, update_values)
        
        # Update details jika diberikan
        if details is not None:
            try:
                details_list = json.loads(details)
                if not isinstance(details_list, list):
                    raise ValueError("Details harus berupa array")
                
                # Hapus semua details lama
                cursor.execute("DELETE FROM contact_details WHERE contact_item_id = %s", (item_id,))
                
                # Insert details baru
                if details_list:
                    for i, detail in enumerate(details_list):
                        if detail and str(detail).strip():  # Hanya insert jika detail tidak kosong
                            cursor.execute("""
                                INSERT INTO contact_details (contact_item_id, detail_text, detail_order)
                                VALUES (%s, %s, %s)
                            """, (item_id, str(detail).strip(), i + 1))
            
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Format details tidak valid: {str(e)}")
        
        connection.commit()
        
        # Ambil data terbaru
        cursor.execute("SET SESSION group_concat_max_len = 1000000")
        cursor.execute("""
            SELECT ci.*, 
                   GROUP_CONCAT(cd.detail_text ORDER BY cd.detail_order SEPARATOR '|||') as details_text
            FROM contact_items ci
            LEFT JOIN contact_details cd ON ci.id = cd.contact_item_id
            WHERE ci.id = %s
            GROUP BY ci.id
        """, (item_id,))
        
        updated_item = cursor.fetchone()
        
        # Format details
        if updated_item and updated_item.get('details_text'):
            details_str = str(updated_item['details_text']) if updated_item['details_text'] else ''
            updated_item['details'] = [d for d in details_str.split('|||') if d]
        else:
            updated_item['details'] = []
        
        # Hapus field sementara
        if updated_item and 'details_text' in updated_item:
            del updated_item['details_text']
        
        return {
            "message": "Contact item berhasil diupdate",
            "contact_item": updated_item
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating contact item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate contact item: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/kontak/contact-items/{item_id}")
def delete_contact_item(
    item_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus contact item (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah item ada
        cursor.execute("SELECT id FROM contact_items WHERE id = %s", (item_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Contact item tidak ditemukan")
        
        # Hapus item (details akan otomatis terhapus karena foreign key cascade atau manual)
        cursor.execute("DELETE FROM contact_items WHERE id = %s", (item_id,))
        connection.commit()
        
        return {
            "message": "Contact item berhasil dihapus",
            "item_id": item_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting contact item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus contact item: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/kontak/reset")
def reset_kontak_content(token: dict = Depends(verify_token)):
    """Reset konten Kontak ke default (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Reset kontak table
        cursor.execute("DELETE FROM kontak")
        cursor.execute("""
            INSERT INTO kontak (hero_title, hero_subtitle, hero_description)
            VALUES (%s, %s, %s)
        """, (
            "Hubungi Kami",
            "Kami Siap Membantu Anda",
            "Punya pertanyaan, saran, atau ingin berkolaborasi? Tim kami siap membantu Anda dengan solusi terbaik untuk kebutuhan event lari Anda."
        ))
        
        # Reset contact_items table
        cursor.execute("DELETE FROM contact_details")
        cursor.execute("DELETE FROM contact_items")
        
        # Insert default contact items
        default_contacts = [
            {
                "icon": "Mail",
                "title": "Email",
                "action_url": "mailto:info@gastronomirun.com",
                "order_position": 1,
                "details": ["info@gastronomirun.com", "support@gastronomirun.com"]
            },
            {
                "icon": "Phone",
                "title": "Telepon",
                "action_url": "tel:+622112345678",
                "order_position": 2,
                "details": ["(021) 1234-5678", "0812-3456-7890"]
            },
            {
                "icon": "MapPin",
                "title": "Alamat",
                "action_url": "https://maps.google.com",
                "order_position": 3,
                "details": ["Jakarta Running Center", "Jl. Sudirman No. 123", "Jakarta Selatan, 12190"]
            },
            {
                "icon": "Clock",
                "title": "Jam Operasional",
                "action_url": None,
                "order_position": 4,
                "details": ["Senin - Jumat: 08:00 - 17:00", "Sabtu: 08:00 - 12:00", "Minggu: Tutup"]
            }
        ]
        
        for contact in default_contacts:
            cursor.execute("""
                INSERT INTO contact_items (icon, title, action_url, order_position, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                contact["icon"],
                contact["title"],
                contact["action_url"],
                contact["order_position"],
                True
            ))
            
            item_id = cursor.lastrowid
            
            # Insert details
            if contact["details"]:
                for i, detail in enumerate(contact["details"]):
                    if detail and detail.strip():
                        cursor.execute("""
                            INSERT INTO contact_details (contact_item_id, detail_text, detail_order)
                            VALUES (%s, %s, %s)
                        """, (item_id, detail.strip(), i + 1))
        
        connection.commit()
        
        return {
            "message": "Data kontak berhasil direset ke default",
            "reset_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting kontak content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mereset data kontak: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/kontak/public")
def get_public_kontak():
    """Get konten Kontak untuk public (tanpa auth)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Set group_concat_max_len untuk menghindari truncation
        cursor.execute("SET SESSION group_concat_max_len = 1000000")
        
        # Ambil data hero section
        cursor.execute("SELECT * FROM kontak ORDER BY id DESC LIMIT 1")
        kontak_data = cursor.fetchone()
        
        if not kontak_data:
            # Return default data jika tidak ada di database
            kontak_data = {
                "hero_title": "Hubungi Kami",
                "hero_subtitle": "Kami Siap Membantu Anda",
                "hero_description": "Punya pertanyaan, saran, atau ingin berkolaborasi? Tim kami siap membantu Anda dengan solusi terbaik untuk kebutuhan event lari Anda."
            }
        
        # Ambil contact items yang aktif dengan details
        create_contact_tables()
        cursor.execute("""
            SELECT ci.*, 
                   GROUP_CONCAT(cd.detail_text ORDER BY cd.detail_order SEPARATOR '|||') as details_text
            FROM contact_items ci
            LEFT JOIN contact_details cd ON ci.id = cd.contact_item_id
            WHERE ci.is_active = TRUE
            GROUP BY ci.id
            ORDER BY ci.order_position ASC
        """)
        contact_items = cursor.fetchall()
        
        # Format details menjadi list
        for item in contact_items:
            if item['details_text']:
                # Hapus None values dan split
                details_str = str(item['details_text']) if item['details_text'] else ''
                item['details'] = [d for d in details_str.split('|||') if d]
            else:
                item['details'] = []
            
            # Hapus field sementara
            if 'details_text' in item:
                del item['details_text']
        
        return {
            "hero_title": kontak_data.get('hero_title', ''),
            "hero_subtitle": kontak_data.get('hero_subtitle', ''),
            "hero_description": kontak_data.get('hero_description', ''),
            "contact_items": contact_items
        }
        
    except Exception as e:
        logger.error(f"Error getting public kontak: {str(e)}")
        # Return default data jika error
        return {
            "hero_title": "Hubungi Kami",
            "hero_subtitle": "Kami Siap Membantu Anda",
            "hero_description": "Punya pertanyaan, saran, atau ingin berkolaborasi? Tim kami siap membantu Anda dengan solusi terbaik untuk kebutuhan event lari Anda.",
            "contact_items": [
                {
                    "id": 1,
                    "icon": "Mail",
                    "title": "Email",
                    "details": ["info@gastronomirun.com", "support@gastronomirun.com"],
                    "action_url": "mailto:info@gastronomirun.com",
                    "order_position": 1,
                    "is_active": True
                },
                {
                    "id": 2,
                    "icon": "Phone",
                    "title": "Telepon",
                    "details": ["(021) 1234-5678", "0812-3456-7890"],
                    "action_url": "tel:+622112345678",
                    "order_position": 2,
                    "is_active": True
                },
                {
                    "id": 3,
                    "icon": "MapPin",
                    "title": "Alamat",
                    "details": ["Jakarta Running Center", "Jl. Sudirman No. 123", "Jakarta Selatan, 12190"],
                    "action_url": "https://maps.google.com",
                    "order_position": 3,
                    "is_active": True
                },
                {
                    "id": 4,
                    "icon": "Clock",
                    "title": "Jam Operasional",
                    "details": ["Senin - Jumat: 08:00 - 17:00", "Sabtu: 08:00 - 12:00", "Minggu: Tutup"],
                    "action_url": None,
                    "order_position": 4,
                    "is_active": True
                }
            ]
        }
    finally:
        cursor.close()
        connection.close()