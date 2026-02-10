from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth import verify_user
from config.database import db
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/home", tags=["Home"])

@router.get("/riwayat")
def get_riwayat_home_user(token: dict = Depends(verify_user)):
    """Endpoint khusus untuk HomeUser - tampilkan hanya riwayat yang BELUM dihapus"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Dapatkan user_id dari token
        user_id = token.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID tidak ditemukan")
        
        # Query: Filter hanya data yang deleted_at IS NULL
        cursor.execute("""
            SELECT 
                b.*, 
                i.nama_barang, 
                i.foto as foto_barang,
                c.nama as kategori_barang,
                r.tanggal_pengembalian, 
                r.kondisi_barang, 
                r.catatan, 
                r.foto as foto_pengembalian,
                r.created_at as tanggal_pengembalian_dibuat,
                CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END as dikembalikan,
                CASE WHEN b.deleted_at IS NOT NULL THEN TRUE ELSE FALSE END as dihapus_admin
            FROM borrowings b 
            JOIN items i ON b.barang_id = i.id 
            JOIN categories c ON i.kategori_id = c.id 
            LEFT JOIN returns r ON b.id = r.borrowing_id
            WHERE b.user_id = %s 
            AND b.deleted_at IS NULL  -- Hanya data yang belum dihapus
            ORDER BY b.created_at DESC
        """, (user_id,))
        
        riwayat = cursor.fetchall()
        
        # Format data
        formatted_data = []
        for item in riwayat:
            formatted_item = dict(item)
            
            # Normalisasi path foto barang
            if item['foto_barang']:
                foto_barang_path = item['foto_barang']
                if foto_barang_path.startswith('uploads\\') or foto_barang_path.startswith('uploads/'):
                    foto_barang_path = foto_barang_path.replace('uploads\\', '').replace('uploads/', '')
                formatted_item['foto_barang'] = foto_barang_path
            
            # Jika ada data pengembalian, format menjadi objek
            if item['dikembalikan'] and item['foto_pengembalian']:
                foto_path = item['foto_pengembalian']
                if foto_path.startswith('uploads\\') or foto_path.startswith('uploads/'):
                    foto_path = foto_path.replace('uploads\\', '').replace('uploads/', '')
                
                formatted_item['pengembalian'] = {
                    'tanggal_pengembalian': item['tanggal_pengembalian'],
                    'kondisi_barang': item['kondisi_barang'],
                    'catatan': item['catatan'],
                    'foto': foto_path,
                    'tanggal_dibuat': item['tanggal_pengembalian_dibuat']
                }
            
            formatted_data.append(formatted_item)
        
        return formatted_data
        
    except Exception as e:
        logger.error(f"Error fetching home riwayat data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data riwayat home: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Endpoint delete dihapus untuk menjaga integritas data statistik