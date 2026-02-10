from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Buat folder uploads jika belum ada
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# Buat subfolder uploads jika belum ada
UPLOAD_SUBFOLDERS = ["slider", "tentang_kami", "tim", "kontak"]
for folder in UPLOAD_SUBFOLDERS:
    folder_path = os.path.join("uploads", folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logger.info(f"Created upload folder: {folder_path}")

# ✅ TAMBAHKAN FOLDER UNTUK PARTNER
PARTNER_FOLDER = "static/uploads/partner"
if not os.path.exists(PARTNER_FOLDER):
    os.makedirs(PARTNER_FOLDER)
    logger.info(f"Created partner folder: {PARTNER_FOLDER}")

app = FastAPI(title="Inventory Management API", version="1.0.0")


def get_allowed_origins():
    origins = os.getenv(
        "CORS_ORIGINS",
        "https://gastronomi.id,https://www.gastronomi.id,https://api.gastronomi.id,http://localhost:5173,http://localhost:3000",
    )
    return [origin.strip() for origin in origins.split(",") if origin.strip()]

# ✅ PERBAIKI: Mount static files untuk uploads dan static
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import dan include semua routers yang sudah ada
from routes.auth import router as auth_router
from routes.kelas import router as kelas_router
from routes.kategori import router as kategori_router
from routes.stok import router as stok_router
from routes.home import router as home_router
from routes.admin_stats import router as admin_stats_router
from routes.admin import router as admin_router

# ✅ IMPORT ROUTERS BARU (admin routes yang sudah dipisah)
from routes.kontak import router as kontak_router
from routes.slider import router as slider_router
from routes.tim import router as tim_router
from routes.tentangkami import router as tentangkami_router
from routes.footerkontak import router as footerkontak_router
from routes.layanan import router as layanan_router
from routes.tiket_kategori import router as tiket_kategori_router
from routes.slider_events import router as slider_events_router
from routes.partner import router as partner_router

# Include semua routers yang sudah ada
app.include_router(auth_router)
app.include_router(kelas_router)
app.include_router(kategori_router)
app.include_router(stok_router)
app.include_router(home_router)
app.include_router(admin_stats_router)
app.include_router(admin_router)

# ✅ INCLUDE ROUTERS BARU (admin routes yang sudah dipisah)
app.include_router(kontak_router)
app.include_router(slider_router)
app.include_router(tim_router)
app.include_router(tentangkami_router)
app.include_router(footerkontak_router)
app.include_router(layanan_router)
app.include_router(tiket_kategori_router)
app.include_router(slider_events_router)
app.include_router(partner_router)

# Health check endpoints
@app.get("/")
def read_root():
    return {
        "message": "Inventory Management API", 
        "status": "running",
        "version": "1.0.0",
        "admin_modules": {
            "kontak": "ready",
            "slider": "ready", 
            "tim": "ready",
            "tentang_kami": "ready",
            "partner": "ready"
        }
    }

@app.get("/health")
def health_check():
    from config.database import db
    connection = None
    cursor = None
    try:
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return {
            "status": "healthy", 
            "database": "connected",
            "upload_folders": UPLOAD_SUBFOLDERS,
            "partner_folder": PARTNER_FOLDER
        }
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/debug/upload-folders")
def debug_upload_folders():
    """Debug endpoint untuk mengecek folder upload"""
    result = {}
    all_folders = UPLOAD_SUBFOLDERS + ["partner"]
    for folder in all_folders:
        if folder == "partner":
            folder_path = PARTNER_FOLDER
        else:
            folder_path = os.path.join("uploads", folder)
        
        exists = os.path.exists(folder_path)
        writable = os.access(folder_path, os.W_OK) if exists else False
        result[folder] = {
            "path": folder_path,
            "exists": exists,
            "writable": writable,
            "file_count": len(os.listdir(folder_path)) if exists and os.path.isdir(folder_path) else 0
        }
    return result

@app.get("/debug/partner-images")
def debug_partner_images():
    """Debug endpoint untuk mengecek gambar partner"""
    try:
        images = []
        if os.path.exists(PARTNER_FOLDER):
            for filename in os.listdir(PARTNER_FOLDER):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    file_path = os.path.join(PARTNER_FOLDER, filename)
                    file_size = os.path.getsize(file_path)
                    images.append({
                        "filename": filename,
                        "url": f"/static/uploads/partner/{filename}",
                        "path": file_path,
                        "size": file_size,
                        "exists": os.path.exists(file_path)
                    })
        
        return {
            "folder": PARTNER_FOLDER,
            "exists": os.path.exists(PARTNER_FOLDER),
            "image_count": len(images),
            "images": images
        }
    except Exception as e:
        return {"error": str(e)}

# Debug endpoints (sudah ada)
@app.get("/debug/barang/{barang_id}")
def debug_barang(barang_id: int):
    """Endpoint untuk debugging status unit barang"""
    from config.database import db
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Get barang info
        cursor.execute("SELECT * FROM items WHERE id = %s", (barang_id,))
        barang = cursor.fetchone()
        if not barang:
            return {"error": "Barang tidak ditemukan"}
        
        # Get all units
        cursor.execute("SELECT * FROM item_units WHERE barang_id = %s", (barang_id,))
        stok_units = cursor.fetchall()
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM item_units 
            WHERE barang_id = %s 
            GROUP BY status
        """, (barang_id,))
        status_count = cursor.fetchall()
        
        return {
            "barang_id": barang_id,
            "nama_barang": barang['nama_barang'],
            "stok_units": stok_units,
            "status_summary": status_count
        }
        
    except Exception as e:
        return {"error": f"Error: {str(e)}"}
    finally:
        cursor.close()
        connection.close()

@app.get("/pengembalian/{peminjaman_id}")
async def get_pengembalian(peminjaman_id: str):
    from config.database import db
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT r.*, b.nama_peminjam, i.nama_barang
            FROM returns r
            JOIN borrowings b ON r.borrowing_id = b.id
            JOIN items i ON b.barang_id = i.id
            WHERE r.borrowing_id = %s
        """, (peminjaman_id,))
        
        pengembalian = cursor.fetchone()
        if not pengembalian:
            raise HTTPException(status_code=404, detail="Belum ada data pengembalian")

        return pengembalian
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
