from fastapi import APIRouter, Depends, HTTPException, Form
from typing import Optional, List
from decimal import Decimal
import logging
from config.database import db
from dependencies.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kelas/tiket-kategori", tags=["Tiket Kategori"])

@router.post("/")
def create_tiket_kategori(
    kelas_id: int = Form(...),
    nama_kategori: str = Form(...),
    deskripsi: str = Form(...),
    harga: float = Form(...),
    manfaat: str = Form(...),
    is_populer: bool = Form(False),
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom is_active ada di tabel
        cursor.execute("SHOW COLUMNS FROM tiket_kategori LIKE 'is_active'")
        has_is_active = cursor.fetchone()
        
        if has_is_active:
            # Kolom is_active ada
            cursor.execute("""
                INSERT INTO tiket_kategori 
                (kelas_id, nama_kategori, deskripsi, harga, manfaat, is_populer, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (kelas_id, nama_kategori, deskripsi, harga, manfaat, is_populer, True))
        else:
            # Kolom is_active tidak ada, gunakan INSERT tanpa is_active
            cursor.execute("""
                INSERT INTO tiket_kategori 
                (kelas_id, nama_kategori, deskripsi, harga, manfaat, is_populer)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (kelas_id, nama_kategori, deskripsi, harga, manfaat, is_populer))
        
        connection.commit()
        tiket_id = cursor.lastrowid
        
        # Get the created tiket with is_active handling
        cursor.execute("""
            SELECT *, 
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori WHERE id = %s
        """, (tiket_id,))
        tiket = cursor.fetchone()
        
        # Convert Decimal to float
        if tiket and isinstance(tiket.get('harga'), Decimal):
            tiket['harga'] = float(tiket['harga'])
        
        # Ensure is_active field exists
        if 'is_active' not in tiket:
            tiket['is_active'] = True
        
        return {
            "message": "Tiket kategori berhasil ditambahkan",
            "tiket": tiket
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error creating tiket kategori: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menambahkan tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/{tiket_id}")
def get_tiket_kategori(tiket_id: int):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Query dengan handling untuk is_active
        cursor.execute("""
            SELECT *,
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori WHERE id = %s
        """, (tiket_id,))
        tiket = cursor.fetchone()
        
        if not tiket:
            raise HTTPException(status_code=404, detail="Tiket kategori tidak ditemukan")
        
        # Convert Decimal to float
        if isinstance(tiket.get('harga'), Decimal):
            tiket['harga'] = float(tiket['harga'])
        
        # Ensure is_active field exists
        if 'is_active' not in tiket:
            tiket['is_active'] = True
        
        return tiket
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tiket kategori: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/{tiket_id}")
def update_tiket_kategori(
    tiket_id: int,
    nama_kategori: str = Form(...),
    deskripsi: str = Form(...),
    harga: float = Form(...),
    manfaat: str = Form(...),
    is_populer: bool = Form(False),
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Check if tiket exists
        cursor.execute("SELECT * FROM tiket_kategori WHERE id = %s", (tiket_id,))
        existing_tiket = cursor.fetchone()
        
        if not existing_tiket:
            raise HTTPException(status_code=404, detail="Tiket kategori tidak ditemukan")
        
        # Update tiket
        cursor.execute("""
            UPDATE tiket_kategori 
            SET nama_kategori = %s, deskripsi = %s, harga = %s, 
                manfaat = %s, is_populer = %s
            WHERE id = %s
        """, (nama_kategori, deskripsi, harga, manfaat, is_populer, tiket_id))
        
        connection.commit()
        
        # Get updated tiket dengan is_active
        cursor.execute("""
            SELECT *,
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori WHERE id = %s
        """, (tiket_id,))
        updated_tiket = cursor.fetchone()
        
        # Convert Decimal to float
        if updated_tiket and isinstance(updated_tiket.get('harga'), Decimal):
            updated_tiket['harga'] = float(updated_tiket['harga'])
        
        # Ensure is_active field exists
        if 'is_active' not in updated_tiket:
            updated_tiket['is_active'] = True
        
        return {
            "message": "Tiket kategori berhasil diperbarui",
            "tiket": updated_tiket
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating tiket kategori: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error memperbarui tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/{tiket_id}")
def delete_tiket_kategori(tiket_id: int, token: str = Depends(verify_token)):
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        # Check if tiket exists
        cursor.execute("SELECT * FROM tiket_kategori WHERE id = %s", (tiket_id,))
        tiket = cursor.fetchone()
        
        if not tiket:
            raise HTTPException(status_code=404, detail="Tiket kategori tidak ditemukan")
        
        # Delete tiket
        cursor.execute("DELETE FROM tiket_kategori WHERE id = %s", (tiket_id,))
        
        connection.commit()
        
        return {"message": "Tiket kategori berhasil dihapus"}
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting tiket kategori: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ENDPOINT BARU: Toggle Active/Nonaktif Status
@router.put("/{tiket_id}/toggle-active")
def toggle_tiket_kategori_active(
    tiket_id: int,
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom is_active ada
        cursor.execute("SHOW COLUMNS FROM tiket_kategori LIKE 'is_active'")
        has_is_active = cursor.fetchone()
        
        if not has_is_active:
            # Kolom is_active tidak ada, tambahkan
            try:
                cursor.execute("""
                    ALTER TABLE tiket_kategori 
                    ADD COLUMN is_active BOOLEAN DEFAULT TRUE
                """)
                connection.commit()
                logger.info("Kolom is_active berhasil ditambahkan ke tabel tiket_kategori")
            except Exception as alter_error:
                # Mungkin kolom sudah ada atau error lain
                logger.warning(f"Gagal menambah kolom is_active: {str(alter_error)}")
        
        # Check if tiket exists dengan handling is_active
        cursor.execute("""
            SELECT *,
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori WHERE id = %s
        """, (tiket_id,))
        tiket = cursor.fetchone()
        
        if not tiket:
            raise HTTPException(status_code=404, detail="Tiket kategori tidak ditemukan")
        
        # Toggle is_active status
        current_status = tiket.get('is_active', True)
        new_status = not current_status
        
        cursor.execute("""
            UPDATE tiket_kategori 
            SET is_active = %s
            WHERE id = %s
        """, (new_status, tiket_id))
        
        connection.commit()
        
        # Get updated tiket
        cursor.execute("""
            SELECT *,
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori WHERE id = %s
        """, (tiket_id,))
        updated_tiket = cursor.fetchone()
        
        # Convert Decimal to float
        if updated_tiket and isinstance(updated_tiket.get('harga'), Decimal):
            updated_tiket['harga'] = float(updated_tiket['harga'])
        
        # Ensure is_active field exists
        if 'is_active' not in updated_tiket:
            updated_tiket['is_active'] = True
        
        status_text = "diaktifkan" if new_status else "dinonaktifkan"
        
        return {
            "message": f"Tiket kategori berhasil {status_text}",
            "tiket": updated_tiket
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error toggling tiket kategori active status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengubah status tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Endpoint untuk mendapatkan semua tiket kategori dari kelas tertentu
@router.get("/kelas/{kelas_id}")
def get_tiket_kategori_by_kelas(kelas_id: int):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT *,
                   CASE 
                     WHEN is_active IS NULL THEN TRUE
                     ELSE is_active 
                   END as is_active
            FROM tiket_kategori 
            WHERE kelas_id = %s 
            ORDER BY harga ASC
        """, (kelas_id,))
        
        tiket_kategori = cursor.fetchall()
        
        for tiket in tiket_kategori:
            if isinstance(tiket.get('harga'), Decimal):
                tiket['harga'] = float(tiket['harga'])
            
            if 'is_populer' not in tiket:
                tiket['is_populer'] = False
            
            if 'is_active' not in tiket:
                tiket['is_active'] = True
        
        return tiket_kategori
        
    except Exception as e:
        logger.error(f"Error getting tiket kategori for kelas {kelas_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()