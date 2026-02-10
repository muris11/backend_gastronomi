from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from dependencies.auth import verify_token
from config.database import db
from utils.file_utils import save_upload_file, delete_file
import logging
import os
from decimal import Decimal
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kelas", tags=["Kelas"])

@router.get("/")
def get_all_kelas():
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # PERBAIKAN: Gunakan k.* untuk mengambil semua kolom yang ada
        cursor.execute("""
            SELECT k.*, c.nama as kategori
            FROM kelas k 
            LEFT JOIN categories c ON k.kategori_id = c.id 
            ORDER BY k.id DESC
        """)
        kelas_list = cursor.fetchall()
        
        # Log untuk debugging
        logger.info(f"Retrieved {len(kelas_list)} kelas from database")
        
        # Ambil peserta dan tiket kategori untuk setiap kelas
        for kelas in kelas_list:
            try:
                # Ambil peserta jika tabel ada
                cursor.execute("SELECT * FROM kelas_peserta WHERE kelas_id = %s", (kelas['id'],))
                kelas['peserta'] = cursor.fetchall()
                # HANYA untuk informasi peserta terdaftar, tidak override total_peserta
            except Exception as e:
                logger.warning(f"Could not fetch peserta for kelas {kelas['id']}: {str(e)}")
                kelas['peserta'] = []
            
            # Ambil tiket kategori
            cursor.execute("""
                SELECT * FROM tiket_kategori 
                WHERE kelas_id = %s 
                ORDER BY harga ASC
            """, (kelas['id'],))
            tiket_kategori = cursor.fetchall()
            
            # Format tiket kategori
            for tiket in tiket_kategori:
                if isinstance(tiket.get('harga'), Decimal):
                    tiket['harga'] = float(tiket['harga'])
                
                # Ensure is_populer field exists
                if 'is_populer' not in tiket:
                    tiket['is_populer'] = False
            
            kelas['tiket_kategori'] = tiket_kategori
            
            # TAMBAHKAN: Link navigasi dari database
            if 'link_navigasi' not in kelas:
                kelas['link_navigasi'] = ''
            if 'is_link_eksternal' not in kelas:
                kelas['is_link_eksternal'] = False
            
            # Debug info untuk foto
            if kelas.get('foto'):
                logger.info(f"Kelas {kelas['id']}: {kelas['nama_kelas']} - Foto: {kelas['foto']}")
                
                # Cek apakah file ada di server
                foto_path = os.path.join("uploads", kelas['foto'])
                if os.path.exists(foto_path):
                    kelas['foto_exists'] = True
                    kelas['foto_url'] = f"http://localhost:8000/uploads/{kelas['foto']}"
                else:
                    kelas['foto_exists'] = False
                    logger.warning(f"File not found: {foto_path}")
                    
            # Tambahkan URL untuk gambar event (gambaran_event)
            if kelas.get('gambaran_event'):
                try:
                    gambaran_event = json.loads(kelas['gambaran_event'])
                    if isinstance(gambaran_event, list):
                        kelas['gambaran_event_urls'] = [
                            f"http://localhost:8000/uploads/{foto}" 
                            for foto in gambaran_event
                        ]
                except json.JSONDecodeError:
                    kelas['gambaran_event_urls'] = []
        
        return kelas_list
        
    except Exception as e:
        logger.error(f"Error getting kelas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data kelas: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/{id}")
def get_kelas(id: int):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT k.*, c.nama as kategori 
            FROM kelas k 
            LEFT JOIN categories c ON k.kategori_id = c.id 
            WHERE k.id = %s
        """, (id,))
        kelas = cursor.fetchone()
        
        if not kelas:
            raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
        
        # TAMBAHKAN: Link navigasi dari database
        if 'link_navigasi' not in kelas:
            kelas['link_navigasi'] = ''
        if 'is_link_eksternal' not in kelas:
            kelas['is_link_eksternal'] = False
        
        # Tambahkan URL foto lengkap
        if kelas.get('foto'):
            kelas['foto_url'] = f"http://localhost:8000/uploads/{kelas['foto']}"
            
            # Cek file existence
            foto_path = os.path.join("uploads", kelas['foto'])
            kelas['foto_exists'] = os.path.exists(foto_path)
        
        # Tambahkan URL untuk gambar event (gambaran_event)
        if kelas.get('gambaran_event'):
            try:
                gambaran_event = json.loads(kelas['gambaran_event'])
                if isinstance(gambaran_event, list):
                    kelas['gambaran_event_urls'] = [
                        f"http://localhost:8000/uploads/{foto}" 
                        for foto in gambaran_event
                    ]
            except json.JSONDecodeError:
                kelas['gambaran_event_urls'] = []
        
        try:
            # Ambil peserta (hanya untuk informasi)
            cursor.execute("SELECT * FROM kelas_peserta WHERE kelas_id = %s", (id,))
            kelas['peserta'] = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Could not fetch peserta for kelas {id}: {str(e)}")
            kelas['peserta'] = []
        
        # Ambil tiket kategori untuk kelas ini
        cursor.execute("""
            SELECT * FROM tiket_kategori 
            WHERE kelas_id = %s 
            ORDER BY harga ASC
        """, (id,))
        tiket_kategori = cursor.fetchall()
        
        # Format tiket kategori
        for tiket in tiket_kategori:
            if isinstance(tiket.get('harga'), Decimal):
                tiket['harga'] = float(tiket['harga'])
            
            # Ensure is_populer field exists
            if 'is_populer' not in tiket:
                tiket['is_populer'] = False
        
        kelas['tiket_kategori'] = tiket_kategori
        
        # Pastikan total_peserta ada (default 0 jika tidak ada)
        if 'total_peserta' not in kelas:
            kelas['total_peserta'] = 0
        
        return kelas
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting kelas {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data kelas: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/")
async def create_kelas(
    nama_kelas: str = Form(...),
    kategori: str = Form(...),
    deskripsi: str = Form(...),
    jadwal: str = Form(...),
    ruangan: str = Form(...),
    biaya: float = Form(...),
    total_peserta: Optional[int] = Form(0),  # Kuota maksimal dari input form
    link_navigasi: str = Form(""),  # TAMBAHKAN: Link navigasi untuk tombol Beli
    is_link_eksternal: bool = Form(False),  # TAMBAHKAN: Apakah link eksternal
    foto: UploadFile = File(None),
    gambaran_event: List[UploadFile] = File([]),
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        logger.info(f"Creating new kelas: {nama_kelas}")
        logger.info(f"Link navigasi: {link_navigasi}, Is external: {is_link_eksternal}")
        
        # Cari atau buat kategori
        cursor.execute("SELECT id FROM categories WHERE nama = %s", (kategori,))
        kategori_result = cursor.fetchone()
        
        if kategori_result:
            kategori_id = kategori_result[0]
            logger.info(f"Using existing kategori ID: {kategori_id}")
        else:
            cursor.execute("INSERT INTO categories (nama) VALUES (%s)", (kategori,))
            kategori_id = cursor.lastrowid
            logger.info(f"Created new kategori ID: {kategori_id}")
        
        # Upload foto kelas
        foto_filename = None
        if foto:
            foto_filename = await save_upload_file(foto, "kelas")
            logger.info(f"Kelas photo saved: {foto_filename}")
        else:
            logger.warning("No photo uploaded for kelas")
        
        # Upload multiple photos untuk gambaran event (maksimal 5)
        gambaran_event_filenames = []
        if gambaran_event and len(gambaran_event) > 0:
            for i, file in enumerate(gambaran_event[:5]):
                if file:
                    filename = await save_upload_file(file, "gambaran_event")
                    gambaran_event_filenames.append(filename)
                    logger.info(f"Gambaran event photo {i+1} saved: {filename}")
        
        # Simpan sebagai JSON string di database
        gambaran_event_json = json.dumps(gambaran_event_filenames) if gambaran_event_filenames else None
        
        # Insert kelas - total_peserta sebagai kuota maksimal
        cursor.execute(
            """INSERT INTO kelas (nama_kelas, kategori_id, deskripsi, jadwal, 
               ruangan, biaya, total_peserta, foto, gambaran_event, link_navigasi, is_link_eksternal) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (nama_kelas, kategori_id, deskripsi, jadwal, ruangan, biaya, 
             total_peserta, foto_filename, gambaran_event_json, link_navigasi, is_link_eksternal)
        )
        kelas_id = cursor.lastrowid
        
        # Buat tiket kategori default otomatis
        tiket_default = [
            {
                "nama_kategori": "Reguler",
                "deskripsi": "Paket standar untuk peserta",
                "harga": float(biaya),
                "manfaat": "Akses kelas lengkap, Materi pembelajaran, Sertifikat elektronik, Akses grup WhatsApp",
                "is_populer": True
            },
            {
                "nama_kategori": "Premium",
                "deskripsi": "Paket lengkap dengan benefit eksklusif",
                "harga": float(biaya) * 1.5,
                "manfaat": "Akses kelas lengkap, Materi pembelajaran premium, Sertifikat fisik, Konsultasi private, Akses grup eksklusif, Merchandise eksklusif",
                "is_populer": False
            },
            {
                "nama_kategori": "Early Bird",
                "deskripsi": "Paket spesial untuk pendaftar awal",
                "harga": float(biaya) * 0.8,
                "manfaat": "Akses kelas lengkap, Materi pembelajaran, Sertifikat elektronik, Bonus e-book materi",
                "is_populer": False
            }
        ]
        
        for tiket in tiket_default:
            cursor.execute("""
                INSERT INTO tiket_kategori 
                (kelas_id, nama_kategori, deskripsi, harga, manfaat, is_populer) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (kelas_id, tiket['nama_kategori'], tiket['deskripsi'], 
                  tiket['harga'], tiket['manfaat'], tiket['is_populer']))
        
        connection.commit()
        
        logger.info(f"Kelas created successfully: ID {kelas_id} with 3 default tiket categories")
        
        # Return response dengan URL foto dan gambaran event
        gambaran_event_urls = [
            f"http://localhost:8000/uploads/{foto}" 
            for foto in gambaran_event_filenames
        ] if gambaran_event_filenames else []
        
        response_data = {
            "message": "Kelas berhasil ditambahkan", 
            "kelas_id": kelas_id,
            "data": {
                "nama_kelas": nama_kelas,
                "total_peserta": total_peserta,
                "link_navigasi": link_navigasi,
                "is_link_eksternal": is_link_eksternal,
                "foto": foto_filename,
                "foto_url": f"http://localhost:8000/uploads/{foto_filename}" if foto_filename else None,
                "gambaran_event": gambaran_event_filenames,
                "gambaran_event_urls": gambaran_event_urls,
                "tiket_kategori_created": len(tiket_default)
            }
        }
        
        return response_data
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error creating kelas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/{kelas_id}")
async def update_kelas(
    kelas_id: int,
    nama_kelas: str = Form(...),
    kategori: str = Form(...),
    deskripsi: str = Form(...),
    jadwal: str = Form(...),
    ruangan: str = Form(...),
    biaya: float = Form(...),
    total_peserta: Optional[int] = Form(0),  # Kuota maksimal dari input form
    link_navigasi: str = Form(""),  # TAMBAHKAN: Link navigasi untuk tombol Beli
    is_link_eksternal: bool = Form(False),  # TAMBAHKAN: Apakah link eksternal
    foto: UploadFile = File(None),
    hapus_foto: bool = Form(False),
    gambaran_event: List[UploadFile] = File([]),
    hapus_gambaran_event: bool = Form(False),
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info(f"Updating kelas ID: {kelas_id}")
        logger.info(f"Link navigasi baru: {link_navigasi}, Is external: {is_link_eksternal}")
        
        # Cek kelas exists
        cursor.execute("SELECT * FROM kelas WHERE id = %s", (kelas_id,))
        kelas = cursor.fetchone()
        if not kelas:
            raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")
        
        logger.info(f"Found kelas: {kelas['nama_kelas']}")
        logger.info(f"Current foto: {kelas.get('foto')}")
        
        # Cari atau buat kategori
        cursor.execute("SELECT id FROM categories WHERE nama = %s", (kategori,))
        kategori_result = cursor.fetchone()
        if kategori_result:
            kategori_id = kategori_result['id']
        else:
            cursor.execute("INSERT INTO categories (nama) VALUES (%s)", (kategori,))
            kategori_id = cursor.lastrowid
        
        # Handle foto kelas
        foto_filename = kelas.get('foto')
        if hapus_foto and foto_filename:
            delete_file(foto_filename)
            foto_filename = None
            logger.info("Deleted kelas photo")
        
        if foto:
            # Hapus foto lama jika ada
            if foto_filename:
                delete_file(foto_filename)
                logger.info(f"Deleted old photo: {foto_filename}")
            
            foto_filename = await save_upload_file(foto, "kelas")
            logger.info(f"Saved new photo: {foto_filename}")
        
        # Handle gambaran event
        gambaran_event_json = kelas.get('gambaran_event')
        gambaran_event_filenames = []
        
        if hapus_gambaran_event and gambaran_event_json:
            try:
                old_files = json.loads(gambaran_event_json)
                for old_file in old_files:
                    delete_file(old_file)
                    logger.info(f"Deleted old gambaran event: {old_file}")
            except json.JSONDecodeError:
                pass
            gambaran_event_json = None
        
        # Jika ada file baru yang diupload
        if gambaran_event and len(gambaran_event) > 0:
            # Hapus file lama jika ada
            if gambaran_event_json:
                try:
                    old_files = json.loads(gambaran_event_json)
                    for old_file in old_files:
                        delete_file(old_file)
                        logger.info(f"Deleted old gambaran event: {old_file}")
                except json.JSONDecodeError:
                    pass
            
            # Upload file baru
            for i, file in enumerate(gambaran_event[:5]):
                if file:
                    filename = await save_upload_file(file, "gambaran_event")
                    gambaran_event_filenames.append(filename)
                    logger.info(f"Gambaran event photo {i+1} saved: {filename}")
            
            gambaran_event_json = json.dumps(gambaran_event_filenames)
        
        # Update kelas - total_peserta sebagai kuota maksimal
        cursor.execute(
            """UPDATE kelas SET nama_kelas = %s, kategori_id = %s, deskripsi = %s, 
               jadwal = %s, ruangan = %s, biaya = %s, total_peserta = %s,
               foto = %s, gambaran_event = %s, link_navigasi = %s, is_link_eksternal = %s WHERE id = %s""",
            (nama_kelas, kategori_id, deskripsi, jadwal, ruangan, biaya, 
             total_peserta, foto_filename, gambaran_event_json, link_navigasi, is_link_eksternal, kelas_id)
        )
        
        connection.commit()
        
        # Get updated kelas data
        cursor.execute("""
            SELECT k.*, c.nama as kategori 
            FROM kelas k 
            LEFT JOIN categories c ON k.kategori_id = c.id 
            WHERE k.id = %s
        """, (kelas_id,))
        updated_kelas = cursor.fetchone()
        
        # Tambahkan URL foto
        if updated_kelas.get('foto'):
            updated_kelas['foto_url'] = f"http://localhost:8000/uploads/{updated_kelas['foto']}"
        
        # Tambahkan URL untuk gambaran event
        if updated_kelas.get('gambaran_event'):
            try:
                gambaran_event = json.loads(updated_kelas['gambaran_event'])
                if isinstance(gambaran_event, list):
                    updated_kelas['gambaran_event_urls'] = [
                        f"http://localhost:8000/uploads/{foto}" 
                        for foto in gambaran_event
                    ]
            except json.JSONDecodeError:
                updated_kelas['gambaran_event_urls'] = []
        
        # Ambil peserta (hanya untuk informasi)
        try:
            cursor.execute("SELECT * FROM kelas_peserta WHERE kelas_id = %s", (kelas_id,))
            updated_kelas['peserta'] = cursor.fetchall()
        except Exception as e:
            logger.warning(f"Could not fetch peserta: {str(e)}")
            updated_kelas['peserta'] = []
        
        # Ambil tiket kategori
        cursor.execute("""
            SELECT * FROM tiket_kategori 
            WHERE kelas_id = %s 
            ORDER BY harga ASC
        """, (kelas_id,))
        tiket_kategori = cursor.fetchall()
        
        # Format tiket kategori
        for tiket in tiket_kategori:
            if isinstance(tiket.get('harga'), Decimal):
                tiket['harga'] = float(tiket['harga'])
            
            if 'is_populer' not in tiket:
                tiket['is_populer'] = False
        
        updated_kelas['tiket_kategori'] = tiket_kategori
        
        logger.info(f"Kelas updated successfully: {kelas_id}")
        
        return {
            "message": "Kelas berhasil diperbarui",
            "kelas": updated_kelas
        }
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating kelas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error memperbarui kelas: {str(e)}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@router.delete("/{id}")
def delete_kelas(id: int, token: str = Depends(verify_token)):
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info(f"Deleting kelas ID: {id}")
        
        cursor.execute("SELECT foto, gambaran_event FROM kelas WHERE id = %s", (id,))
        kelas = cursor.fetchone()
        if not kelas:
            raise HTTPException(status_code=404, detail="Kelas tidak ditemukan")

        # Hapus foto kelas jika ada
        if kelas.get('foto'):
            logger.info(f"Deleting foto: {kelas['foto']}")
            delete_file(kelas['foto'])
        
        # Hapus gambaran event jika ada
        if kelas.get('gambaran_event'):
            try:
                gambaran_event = json.loads(kelas['gambaran_event'])
                if isinstance(gambaran_event, list):
                    for file in gambaran_event:
                        logger.info(f"Deleting gambaran event: {file}")
                        delete_file(file)
            except json.JSONDecodeError:
                pass
        
        # Hapus tiket kategori terkait
        cursor.execute("DELETE FROM tiket_kategori WHERE kelas_id = %s", (id,))
        
        # Hapus data peserta terkait
        try:
            cursor.execute("DELETE FROM kelas_peserta WHERE kelas_id = %s", (id,))
        except Exception as e:
            logger.warning(f"Could not delete peserta: {str(e)}")
        
        # Hapus kelas
        cursor.execute("DELETE FROM kelas WHERE id = %s", (id,))
        
        connection.commit()
        
        logger.info(f"Kelas deleted successfully: {id}")
        
        return {"message": "Kelas berhasil dihapus"}
        
    except HTTPException:
        connection.rollback()
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting kelas: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus kelas: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/image/{kelas_id}")
def get_kelas_image(kelas_id: int):
    """Get image for specific kelas"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT foto FROM kelas WHERE id = %s", (kelas_id,))
        result = cursor.fetchone()
        
        if not result or not result.get('foto'):
            raise HTTPException(status_code=404, detail="Gambar tidak ditemukan")
        
        foto_path = result['foto']
        full_path = os.path.join("uploads", foto_path)
        
        if not os.path.exists(full_path):
            possible_paths = [
                full_path,
                os.path.join("uploads", "kelas", os.path.basename(foto_path)),
                foto_path
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    full_path = path
                    break
            else:
                raise HTTPException(status_code=404, detail="File gambar tidak ditemukan")
        
        from fastapi.responses import FileResponse
        return FileResponse(full_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image for kelas {kelas_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil gambar: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/{kelas_id}/tiket-kategori")
def get_tiket_kategori_kelas(kelas_id: int):
    """Get all tiket kategori for a specific kelas"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM tiket_kategori 
            WHERE kelas_id = %s 
            ORDER BY harga ASC
        """, (kelas_id,))
        
        tiket_kategori = cursor.fetchall()
        
        for tiket in tiket_kategori:
            if isinstance(tiket.get('harga'), Decimal):
                tiket['harga'] = float(tiket['harga'])
            
            if 'is_populer' not in tiket:
                tiket['is_populer'] = False
        
        logger.info(f"Retrieved {len(tiket_kategori)} tiket kategori for kelas {kelas_id}")
        return tiket_kategori
        
    except Exception as e:
        logger.error(f"Error getting tiket kategori for kelas {kelas_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil tiket kategori: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============ ENDPOINT PUBLIC UNTUK USER ============
@router.get("/{kelas_id}/public")
def get_kelas_public(kelas_id: int):
    """
    Endpoint public untuk mendapatkan data kelas tanpa authentication
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info(f"Fetching kelas data for public: ID {kelas_id}")
        
        # PERBAIKAN: Hanya kolom yang pasti ada di tabel kelas
        cursor.execute("""
            SELECT 
                k.id,
                k.nama_kelas,
                k.deskripsi,
                k.jadwal,
                k.ruangan,
                k.biaya,
                k.foto,
                k.created_at,
                k.total_peserta,
                k.link_navigasi,  -- TAMBAHKAN: Link navigasi
                k.is_link_eksternal,  -- TAMBAHKAN: Apakah link eksternal
                c.nama as kategori,
                CONCAT('http://localhost:8000/uploads/', k.foto) as foto_url
            FROM kelas k
            LEFT JOIN categories c ON k.kategori_id = c.id
            WHERE k.id = %s
        """, (kelas_id,))
        
        kelas_data = cursor.fetchone()
        
        if not kelas_data:
            logger.warning(f"Kelas ID {kelas_id} not found")
            return {
                "id": kelas_id,
                "nama_kelas": f"Event {kelas_id}",
                "kategori": "Unknown",
                "foto": None,
                "foto_url": None,
                "jadwal": "",
                "ruangan": "",
                "biaya": 0,
                "total_peserta": 0,
                "link_navigasi": "",  # Default kosong
                "is_link_eksternal": False,  # Default false
                "deskripsi": "",
                "gambaran_event_urls": [],
                "tiket_kategori": []
            }
        
        # Tambahkan field default yang mungkin tidak ada di tabel
        kelas_data['kuota'] = kelas_data.get('total_peserta', 50)  # Gunakan total_peserta sebagai kuota
        kelas_data['durasi'] = "2 jam"  # Default
        
        # Handle gambaran_event
        gambaran_event_urls = []
        if kelas_data.get('gambaran_event'):
            try:
                gambaran_event = json.loads(kelas_data['gambaran_event'])
                if isinstance(gambaran_event, list):
                    gambaran_event_urls = [
                        f"http://localhost:8000/uploads/{foto}" 
                        for foto in gambaran_event if foto
                    ]
            except (json.JSONDecodeError, TypeError):
                pass
        
        kelas_data['gambaran_event_urls'] = gambaran_event_urls
        
        # Ambil tiket kategori
        try:
            cursor.execute("""
                SELECT 
                    id,
                    nama_kategori,
                    deskripsi,
                    harga,
                    manfaat,
                    COALESCE(is_populer, FALSE) as is_populer,
                    COALESCE(is_active, TRUE) as is_active
                FROM tiket_kategori 
                WHERE kelas_id = %s 
                ORDER BY harga ASC
            """, (kelas_id,))
            
            tiket_kategori = cursor.fetchall()
            
            for tiket in tiket_kategori:
                if isinstance(tiket.get('harga'), Decimal):
                    tiket['harga'] = float(tiket['harga'])
            
            kelas_data['tiket_kategori'] = tiket_kategori
        except Exception as e:
            logger.warning(f"Could not fetch tiket kategori for kelas {kelas_id}: {str(e)}")
            kelas_data['tiket_kategori'] = []
        
        logger.info(f"Successfully retrieved kelas data for ID {kelas_id}")
        return kelas_data
        
    except Exception as e:
        logger.error(f"Error getting kelas public data for ID {kelas_id}: {str(e)}", exc_info=True)
        return {
            "id": kelas_id,
            "nama_kelas": f"Event {kelas_id}",
            "kategori": "Error",
            "foto": None,
            "foto_url": None,
            "jadwal": "",
            "ruangan": "",
            "biaya": 0,
            "total_peserta": 0,
            "link_navigasi": "",  # Default kosong
            "is_link_eksternal": False,  # Default false
            "deskripsi": "",
            "gambaran_event_urls": [],
            "tiket_kategori": []
        }
    finally:
        cursor.close()
        connection.close()

@router.get("/public/all")
def get_all_kelas_public(
    kategori: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Endpoint public untuk mendapatkan semua kelas tanpa authentication
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info(f"Fetching all kelas data for public, kategori: {kategori}")
        
        query = """
            SELECT 
                k.id,
                k.nama_kelas,
                k.deskripsi,
                k.jadwal,
                k.ruangan,
                k.biaya,
                k.foto,
                k.total_peserta,
                k.link_navigasi,  -- TAMBAHKAN: Link navigasi
                k.is_link_eksternal,  -- TAMBAHKAN: Apakah link eksternal
                k.created_at,
                c.nama as kategori,
                CONCAT('http://localhost:8000/uploads/', k.foto) as foto_url
            FROM kelas k
            LEFT JOIN categories c ON k.kategori_id = c.id
            WHERE 1=1
        """
        
        params = []
        
        if kategori:
            query += " AND c.nama = %s"
            params.append(kategori)
        
        query += " ORDER BY k.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        kelas_list = cursor.fetchall()
        
        for kelas in kelas_list:
            # Tambahkan field default
            kelas['kuota'] = kelas.get('total_peserta', 50)  # Gunakan total_peserta sebagai kuota
            kelas['durasi'] = "2 jam"
            
            gambaran_event_urls = []
            if kelas.get('gambaran_event'):
                try:
                    gambaran_event = json.loads(kelas['gambaran_event'])
                    if isinstance(gambaran_event, list):
                        gambaran_event_urls = [
                            f"http://localhost:8000/uploads/{foto}" 
                            for foto in gambaran_event if foto
                        ]
                except (json.JSONDecodeError, TypeError):
                    pass
            
            kelas['gambaran_event_urls'] = gambaran_event_urls
        
        logger.info(f"Successfully retrieved {len(kelas_list)} kelas for public")
        return kelas_list
        
    except Exception as e:
        logger.error(f"Error getting all kelas public data: {str(e)}", exc_info=True)
        return []
    finally:
        cursor.close()
        connection.close()