from fastapi import APIRouter, Depends, HTTPException, Form
from typing import List, Optional
from dependencies.auth import verify_token
from config.database import db
from utils.validators import validate_kondisi_barang, normalize_kondisi, validate_status_unit
import logging
from models.enums import KondisiBarang, StatusUnit

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Stok"])

@router.get("/barang/{barang_id}/stok")
def get_barang_stok(barang_id: int):
    """Ambil semua unit stok yang status == 'Tersedia'"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM item_units WHERE barang_id = %s AND status = 'Tersedia'", (barang_id,))
    units = cursor.fetchall()
    
    cursor.close()
    connection.close()
    return {"barang_id": barang_id, "units": units}

@router.put("/barang/{barang_id}/stok/{unit_kode}")
def update_unit_stok(
    barang_id: int,
    unit_kode: str,
    kondisi: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah unit exists
        cursor.execute("""
            SELECT iu.*, i.nama_barang 
            FROM item_units iu 
            JOIN items i ON iu.barang_id = i.id 
            WHERE iu.barang_id = %s AND iu.kode = %s
        """, (barang_id, unit_kode))
        
        unit = cursor.fetchone()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit stok tidak ditemukan")

        # Update fields
        update_fields = []
        params = []
        
        if kondisi is not None:
            # Normalize kondisi value
            kondisi_normalized = normalize_kondisi(kondisi)
            # Validasi kondisi
            if not validate_kondisi_barang(kondisi_normalized):
                kondisi_valid = [k.value for k in KondisiBarang]
                raise HTTPException(
                    status_code=400, 
                    detail=f"Kondisi tidak valid. Pilihan: {', '.join(kondisi_valid)}"
                )
            update_fields.append("kondisi = %s")
            params.append(kondisi_normalized)
        
        if status is not None:
            # Validasi status
            if not validate_status_unit(status):
                status_valid = [s.value for s in StatusUnit]
                raise HTTPException(
                    status_code=400, 
                    detail=f"Status tidak valid. Pilihan: {', '.join(status_valid)}"
                )
            update_fields.append("status = %s")
            params.append(status)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="Tidak ada field yang diupdate")
        
        params.extend([unit_kode, barang_id])
        
        # Update database
        query = f"UPDATE item_units SET {', '.join(update_fields)} WHERE kode = %s AND barang_id = %s"
        cursor.execute(query, params)
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unit stok tidak ditemukan")
        
        # Get updated unit data
        cursor.execute("SELECT * FROM item_units WHERE kode = %s AND barang_id = %s", (unit_kode, barang_id))
        updated_unit = cursor.fetchone()
        
        connection.commit()

        return {
            "message": "Unit stok berhasil diperbarui",
            "unit": updated_unit
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating unit stok: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error memperbarui unit stok: {str(e)}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@router.put("/debug/barang/{barang_id}/stok/{unit_kode}")
def debug_update_unit_stok(
    barang_id: int,
    unit_kode: str,
    kondisi: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    token: str = Depends(verify_token)
):
    """Debug endpoint untuk melihat data yang diterima"""
    return {
        "received_data": {
            "barang_id": barang_id,
            "unit_kode": unit_kode,
            "kondisi": kondisi,
            "status": status,
            "kondisi_type": type(kondisi).__name__,
            "status_type": type(status).__name__,
        },
        "message": "Debug data received"
    }

@router.get("/barang/{barang_id}/stok/{unit_kode}")
def get_unit_stok(barang_id: int, unit_kode: str):
    """Ambil detail unit stok tertentu"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT iu.*, i.nama_barang 
            FROM item_units iu 
            JOIN items i ON iu.barang_id = i.id 
            WHERE iu.barang_id = %s AND iu.kode = %s
        """, (barang_id, unit_kode))
        
        unit = cursor.fetchone()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit stok tidak ditemukan")

        return unit
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/barang/{barang_id}/stok/{unit_kode}")
def delete_unit_stok(barang_id: int, unit_kode: str, token: str = Depends(verify_token)):
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("DELETE FROM item_units WHERE kode = %s AND barang_id = %s", (unit_kode, barang_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unit stok tidak ditemukan")
        
        connection.commit()
        return {"message": "Unit stok berhasil dihapus"}
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/barang/{barang_id}/stok/bulk-delete")
def bulk_delete_stok(barang_id: int, unit_kodes: List[str], token: str = Depends(verify_token)):
    """Hapus banyak unit stok sekaligus"""
    if not unit_kodes:
        raise HTTPException(status_code=400, detail="Daftar unit_kodes tidak boleh kosong")

    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        # Hitung jumlah unit sebelum delete
        cursor.execute("SELECT COUNT(*) FROM item_units WHERE barang_id = %s", (barang_id,))
        before_count = cursor.fetchone()[0]

        # Delete multiple units
        placeholders = ', '.join(['%s'] * len(unit_kodes))
        query = f"DELETE FROM item_units WHERE barang_id = %s AND kode IN ({placeholders})"
        cursor.execute(query, [barang_id] + unit_kodes)
        
        deleted_count = cursor.rowcount
        
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Tidak ada unit stok yang dihapus")

        # Hitung jumlah unit setelah delete
        cursor.execute("SELECT COUNT(*) FROM item_units WHERE barang_id = %s", (barang_id,))
        after_count = cursor.fetchone()[0]

        connection.commit()

        return {
            "message": f"{deleted_count} unit stok berhasil dihapus",
            "barang_id": barang_id,
            "sisa_stok": after_count
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()