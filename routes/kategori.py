from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from dependencies.auth import verify_token
from config.database import db
from utils.file_utils import save_upload_file
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kategori", tags=["Kategori"])

@router.get("/")
def get_kategori():
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM categories ORDER BY nama")
    categories = cursor.fetchall()
    cursor.close()
    connection.close()
    return [cat['nama'] for cat in categories]

@router.post("/")
async def create_kategori_dan_kelas(
    nama_kategori: str = Form(...),
    nama_kelas: str = Form(...),
    deskripsi: str = Form(...),
    jadwal: str = Form(...),
    ruangan: str = Form(...),
    biaya: float = Form(...),
    foto_qr: UploadFile = File(None),  # Ganti metode_pembayaran dengan foto_qr
    foto: UploadFile = File(None),
    token: Optional[str] = Depends(verify_token)
):
    nama_kategori = nama_kategori.strip()
    if not nama_kategori:
        raise HTTPException(status_code=400, detail="Nama kategori kosong")
    
    # Validasi required fields
    required_fields = {
        "nama_kelas": nama_kelas,
        "deskripsi": deskripsi,
        "jadwal": jadwal,
        "ruangan": ruangan,
    }
    
    for field_name, value in required_fields.items():
        if not value or not value.strip():
            raise HTTPException(status_code=400, detail=f"Field {field_name} tidak boleh kosong")
    
    if biaya < 0:
        raise HTTPException(status_code=400, detail="Biaya tidak boleh negatif")
    
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        # Insert kategori jika belum ada
        cursor.execute("INSERT IGNORE INTO categories (nama) VALUES (%s)", (nama_kategori,))
        
        # Dapatkan kategori_id
        cursor.execute("SELECT id FROM categories WHERE nama = %s", (nama_kategori,))
        kategori = cursor.fetchone()
        kategori_id = kategori[0]
        
        # Upload foto QR
        foto_qr_filename = None
        if foto_qr:
            foto_qr_filename = await save_upload_file(foto_qr, "qr_codes")
        
        # Upload foto kelas
        foto_filename = None
        if foto:
            foto_filename = await save_upload_file(foto, "kelas")
        
        # Insert kelas pertama (metode_pembayaran diisi dengan nama file QR)
        cursor.execute(
            """INSERT INTO kelas (nama_kelas, kategori_id, deskripsi, jadwal, 
               ruangan, biaya, metode_pembayaran, foto) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (nama_kelas.strip(), kategori_id, deskripsi.strip(), jadwal.strip(), 
             ruangan.strip(), biaya, foto_qr_filename, foto_filename)
        )
        kelas_id = cursor.lastrowid
        
        connection.commit()
        
        return {
            "message": "Kategori & kelas pertama berhasil ditambahkan",
            "kategori": nama_kategori,
            "kelas_id": kelas_id
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error creating kategori dan kelas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/{nama}")
def delete_kategori(nama: str, token: str = Depends(verify_token)):
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        # Cek apakah kategori digunakan oleh kelas
        cursor.execute("""
            SELECT COUNT(*) 
            FROM kelas k 
            JOIN categories c ON k.kategori_id = c.id 
            WHERE c.nama = %s
        """, (nama,))
        kelas_count = cursor.fetchone()[0]
        
        # Cek apakah kategori digunakan oleh barang (jika masih ada tabel items)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM items i 
            JOIN categories c ON i.kategori_id = c.id 
            WHERE c.nama = %s
        """, (nama,))
        barang_count = cursor.fetchone()[0]
        
        total_count = kelas_count + barang_count
        
        if total_count > 0:
            error_message = f"Kategori '{nama}' masih digunakan oleh "
            if kelas_count > 0:
                error_message += f"{kelas_count} kelas"
                if barang_count > 0:
                    error_message += f" dan {barang_count} barang"
            elif barang_count > 0:
                error_message += f"{barang_count} barang"
            raise HTTPException(status_code=400, detail=error_message)
        
        # Hapus kategori (hanya jika tidak ada kelas atau barang yang menggunakan)
        cursor.execute("DELETE FROM categories WHERE nama = %s", (nama,))
        connection.commit()
        
        return {"message": "Kategori berhasil dihapus", "kategori": nama}
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting kategori: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()