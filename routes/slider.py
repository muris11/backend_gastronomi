# app/routes/admin/slider.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime
import logging
import os
import shutil
import json
from PIL import Image
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin - Slider"])

# Path untuk menyimpan file upload
SLIDER_UPLOAD_DIR = "uploads/slider"
TENTANG_KAMI_UPLOAD_DIR = "uploads/tentang_kami"
os.makedirs(SLIDER_UPLOAD_DIR, exist_ok=True)
os.makedirs(TENTANG_KAMI_UPLOAD_DIR, exist_ok=True)

# Konfigurasi gambar
SLIDER_TARGET_WIDTH = 1200
SLIDER_TARGET_HEIGHT = 600
SLIDER_ASPECT_RATIO = SLIDER_TARGET_WIDTH / SLIDER_TARGET_HEIGHT

# ✅ FUNGSI BARU: Deteksi orientasi gambar
def detect_image_orientation(image_path: str) -> str:
    """Deteksi orientasi gambar (portrait/landscape/square)"""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height > width * 1.1:  # Margin 10% untuk portrait
                return "portrait"
            elif width > height * 1.1:  # Margin 10% untuk landscape
                return "landscape"
            else:
                return "square"
    except Exception as e:
        logger.error(f"Error detecting image orientation: {str(e)}")
        return "unknown"

# ✅ FUNGSI BARU: Get dimensi gambar
def get_image_dimensions(image_path: str):
    """Get dimensi gambar (width, height)"""
    try:
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except Exception as e:
        logger.error(f"Error getting image dimensions: {str(e)}")
        return (0, 0)

# ✅ FUNGSI BARU: Auto-crop gambar ke aspect ratio slider
def auto_crop_to_slider_ratio(image_path: str, output_path: str = None):
    """
    Auto-crop gambar ke aspect ratio slider (2:1)
    Untuk portrait: crop bagian tengah secara vertikal
    Untuk landscape: crop bagian tengah secara horizontal
    """
    try:
        if output_path is None:
            output_path = image_path
            
        with Image.open(image_path) as img:
            # Convert ke RGB jika perlu
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            current_aspect = width / height
            
            # Jika aspect ratio sudah sesuai, hanya resize
            if abs(current_aspect - SLIDER_ASPECT_RATIO) < 0.1:
                img_resized = img.resize((SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT), Image.Resampling.LANCZOS)
                img_resized.save(output_path, quality=95, optimize=True)
                return {
                    "action": "resized",
                    "original_size": (width, height),
                    "new_size": (SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT)
                }
            
            # Hitung crop area
            if current_aspect > SLIDER_ASPECT_RATIO:
                # Gambar terlalu lebar (landscape ekstrem)
                new_width = int(height * SLIDER_ASPECT_RATIO)
                left = (width - new_width) // 2
                top = 0
                right = left + new_width
                bottom = height
            else:
                # Gambar terlalu tinggi (portrait)
                new_height = int(width / SLIDER_ASPECT_RATIO)
                left = 0
                top = (height - new_height) // 2
                right = width
                bottom = top + new_height
            
            # Crop gambar
            crop_box = (left, top, right, bottom)
            img_cropped = img.crop(crop_box)
            
            # Resize ke ukuran target
            img_resized = img_cropped.resize((SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT), Image.Resampling.LANCZOS)
            img_resized.save(output_path, quality=95, optimize=True)
            
            return {
                "action": "cropped_and_resized",
                "original_size": (width, height),
                "crop_area": crop_box,
                "new_size": (SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT)
            }
            
    except Exception as e:
        logger.error(f"Error auto-cropping image: {str(e)}")
        return None

# ✅ FUNGSI BARU: Proses gambar dengan smart cropping
def process_slider_image(file_path: str, crop_mode: str = "smart") -> dict:
    """
    Proses gambar slider dengan berbagai mode crop
    Modes: 'smart', 'crop', 'fit', 'fill'
    """
    try:
        original_dimensions = get_image_dimensions(file_path)
        orientation = detect_image_orientation(file_path)
        
        if crop_mode == "smart":
            # Smart mode: auto-crop untuk portrait, resize untuk landscape
            if orientation == "portrait":
                result = auto_crop_to_slider_ratio(file_path)
                if result:
                    return {
                        **result,
                        "orientation": orientation,
                        "crop_mode": crop_mode
                    }
            else:
                # Untuk landscape, hanya resize
                with Image.open(file_path) as img:
                    # Convert ke RGB jika perlu
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    img_resized = img.resize((SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT), Image.Resampling.LANCZOS)
                    img_resized.save(file_path, quality=95, optimize=True)
                    
                    return {
                        "action": "resized",
                        "original_size": original_dimensions,
                        "new_size": (SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT),
                        "orientation": orientation,
                        "crop_mode": crop_mode
                    }
        
        elif crop_mode == "fit":
            # Fit mode: maintain aspect ratio, add padding
            with Image.open(file_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Calculate scaling factor
                width_ratio = SLIDER_TARGET_WIDTH / img.width
                height_ratio = SLIDER_TARGET_HEIGHT / img.height
                scale_factor = min(width_ratio, height_ratio)
                
                new_width = int(img.width * scale_factor)
                new_height = int(img.height * scale_factor)
                
                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create new image with padding
                new_img = Image.new('RGB', (SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT), (255, 255, 255))
                paste_x = (SLIDER_TARGET_WIDTH - new_width) // 2
                paste_y = (SLIDER_TARGET_HEIGHT - new_height) // 2
                new_img.paste(img_resized, (paste_x, paste_y))
                
                new_img.save(file_path, quality=95, optimize=True)
                
                return {
                    "action": "fitted_with_padding",
                    "original_size": original_dimensions,
                    "new_size": (SLIDER_TARGET_WIDTH, SLIDER_TARGET_HEIGHT),
                    "padding": (paste_x, paste_y),
                    "orientation": orientation,
                    "crop_mode": crop_mode
                }
        
        # Default: auto-crop
        result = auto_crop_to_slider_ratio(file_path)
        if result:
            result["orientation"] = orientation
            result["crop_mode"] = crop_mode
            return result
        
        return {
            "action": "none",
            "original_size": original_dimensions,
            "new_size": original_dimensions,
            "orientation": orientation,
            "crop_mode": "none"
        }
        
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {
            "action": "error",
            "error": str(e),
            "orientation": "unknown"
        }

# ✅ Update tabel database untuk menambahkan kolom orientasi
def update_slider_table_structure():
    """Update struktur tabel event_slider untuk menambahkan kolom orientasi dan dimensi"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah kolom orientation sudah ada
        cursor.execute("SHOW COLUMNS FROM event_slider LIKE 'orientation'")
        orientation_exists = cursor.fetchone() is not None
        
        if not orientation_exists:
            cursor.execute("""
                ALTER TABLE event_slider 
                ADD COLUMN orientation VARCHAR(20),
                ADD COLUMN image_width INT,
                ADD COLUMN image_height INT,
                ADD COLUMN crop_mode VARCHAR(20) DEFAULT 'smart',
                ADD COLUMN processed BOOLEAN DEFAULT FALSE
            """)
            connection.commit()
            logger.info("✅ Added orientation and dimension columns to event_slider table")
            
    except Exception as e:
        logger.error(f"Error updating table structure: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ✅ Update tabel database untuk tentang_kami_slider
def update_tentang_kami_slider_structure():
    """Update struktur tabel tentang_kami_slider"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah tabel tentang_kami_slider sudah ada
        cursor.execute("SHOW TABLES LIKE 'tentang_kami_slider'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            cursor.execute("""
                CREATE TABLE tentang_kami_slider (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    original_name VARCHAR(255) NOT NULL,
                    description TEXT,
                    order_position INT DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    orientation VARCHAR(20),
                    image_width INT,
                    image_height INT,
                    crop_mode VARCHAR(20) DEFAULT 'smart',
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            connection.commit()
            logger.info("✅ Created tentang_kami_slider table")
            
    except Exception as e:
        logger.error(f"Error updating tentang_kami_slider structure: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ENDPOINT UNTUK SLIDER FOTO MANAJEMEN EVENT
# ============================================

@router.get("/admin/slider")
def get_slider_images(token: dict = Depends(verify_token)):
    """Get semua gambar slider (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Update struktur tabel jika diperlukan
    update_slider_table_structure()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada (dengan kolom tambahan)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_slider (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                original_name VARCHAR(255) NOT NULL,
                description TEXT,
                order_position INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                orientation VARCHAR(20),
                image_width INT,
                image_height INT,
                crop_mode VARCHAR(20) DEFAULT 'smart',
                processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            SELECT * FROM event_slider 
            ORDER BY order_position ASC, created_at DESC
        """)
        
        sliders = cursor.fetchall()
        
        # Proses gambar yang belum diproses
        for slider in sliders:
            slider['url'] = f"http://localhost:8000/uploads/slider/{slider['filename']}"
            
            file_path = os.path.join(SLIDER_UPLOAD_DIR, slider['filename'])
            
            # Jika belum diproses, proses sekarang
            if os.path.exists(file_path) and not slider.get('processed'):
                try:
                    # Proses gambar
                    process_result = process_slider_image(file_path, slider.get('crop_mode', 'smart'))
                    
                    if process_result:
                        # Update database dengan informasi baru
                        cursor.execute("""
                            UPDATE event_slider 
                            SET orientation = %s, image_width = %s, image_height = %s, 
                                crop_mode = %s, processed = TRUE, updated_at = %s 
                            WHERE id = %s
                        """, (
                            process_result.get('orientation', 'unknown'),
                            process_result.get('new_size', (0, 0))[0],
                            process_result.get('new_size', (0, 0))[1],
                            process_result.get('crop_mode', 'smart'),
                            datetime.now(),
                            slider['id']
                        ))
                        
                        slider['orientation'] = process_result.get('orientation', 'unknown')
                        slider['image_width'] = process_result.get('new_size', (0, 0))[0]
                        slider['image_height'] = process_result.get('new_size', (0, 0))[1]
                        slider['processed'] = True
                        slider['crop_mode'] = process_result.get('crop_mode', 'smart')
                        slider['process_result'] = process_result
                except Exception as e:
                    logger.error(f"Error processing slider {slider['id']}: {str(e)}")
                    slider['orientation'] = 'error'
        
        connection.commit()
        
        # Ambil data terbaru setelah update
        cursor.execute("""
            SELECT * FROM event_slider 
            ORDER BY order_position ASC, created_at DESC
        """)
        sliders = cursor.fetchall()
        
        # Tambahkan URL dan info untuk setiap slider
        for slider in sliders:
            slider['url'] = f"http://localhost:8000/uploads/slider/{slider['filename']}"
            slider['aspect_ratio'] = SLIDER_ASPECT_RATIO
            slider['target_width'] = SLIDER_TARGET_WIDTH
            slider['target_height'] = SLIDER_TARGET_HEIGHT
            
            # Set default jika tidak ada
            if not slider.get('orientation'):
                slider['orientation'] = 'unknown'
            if not slider.get('crop_mode'):
                slider['crop_mode'] = 'smart'
        
        return sliders
        
    except Exception as e:
        logger.error(f"Error getting slider images: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil gambar slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/admin/slider")
async def upload_slider_image(
    file: UploadFile = File(...),
    description: str = Form(None),
    order_position: int = Form(0),
    crop_mode: str = Form("smart"),
    token: dict = Depends(verify_token)
):
    """Upload gambar slider baru (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi file
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File harus berupa gambar")
    
    # Validasi ukuran file (max 10MB)
    file.file.seek(0, 2)  # Pindah ke akhir file
    file_size = file.file.tell()
    file.file.seek(0)  # Kembali ke awal file
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB")
    
    # Validasi crop mode
    valid_crop_modes = ['smart', 'crop', 'fit', 'fill']
    if crop_mode not in valid_crop_modes:
        crop_mode = 'smart'
    
    # Generate nama file unik
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{token['user_id']}.{file_extension}"
    
    # Simpan file
    file_path = os.path.join(SLIDER_UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan file: {str(e)}")
    
    # Update struktur tabel
    update_slider_table_structure()
    
    # Simpan ke database (tanpa info orientasi dulu)
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            INSERT INTO event_slider 
            (filename, original_name, description, order_position, crop_mode)
            VALUES (%s, %s, %s, %s, %s)
        """, (unique_filename, file.filename, description, order_position, crop_mode))
        
        connection.commit()
        
        slider_id = cursor.lastrowid
        
        # Proses gambar sesuai crop mode
        process_result = process_slider_image(file_path, crop_mode)
        
        # Dapatkan dimensi dan orientasi setelah diproses
        orientation = detect_image_orientation(file_path)
        dimensions = get_image_dimensions(file_path)
        
        # Update database dengan info lengkap
        cursor.execute("""
            UPDATE event_slider 
            SET orientation = %s, image_width = %s, image_height = %s, 
                processed = TRUE, updated_at = %s 
            WHERE id = %s
        """, (orientation, dimensions[0], dimensions[1], datetime.now(), slider_id))
        
        connection.commit()
        
        return {
            "message": "Gambar slider berhasil diupload dan diproses",
            "slider_id": slider_id,
            "filename": unique_filename,
            "url": f"http://localhost:8000/uploads/slider/{unique_filename}",
            "orientation": orientation,
            "dimensions": {
                "width": dimensions[0],
                "height": dimensions[1]
            },
            "crop_mode": crop_mode,
            "process_result": process_result,
            "aspect_ratio": SLIDER_ASPECT_RATIO
        }
        
    except Exception as e:
        # Hapus file jika gagal menyimpan ke database
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.error(f"Error saving to database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan ke database: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/slider/{slider_id}")
async def update_slider_image(
    slider_id: int,
    description: str = Form(None),
    order_position: int = Form(None),
    is_active: bool = Form(None),
    crop_mode: str = Form(None),
    reprocess: bool = Form(False),
    token: dict = Depends(verify_token)
):
    """Update informasi slider (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah slider ada
        cursor.execute("SELECT * FROM event_slider WHERE id = %s", (slider_id,))
        slider = cursor.fetchone()
        
        if not slider:
            raise HTTPException(status_code=404, detail="Slider tidak ditemukan")
        
        # Jika reprocess diminta, proses ulang gambar
        if reprocess:
            file_path = os.path.join(SLIDER_UPLOAD_DIR, slider['filename'])
            if os.path.exists(file_path):
                crop_mode_to_use = crop_mode if crop_mode else slider.get('crop_mode', 'smart')
                process_result = process_slider_image(file_path, crop_mode_to_use)
                
                if process_result:
                    orientation = detect_image_orientation(file_path)
                    dimensions = get_image_dimensions(file_path)
                    
                    # Update dengan data baru
                    cursor.execute("""
                        UPDATE event_slider 
                        SET orientation = %s, image_width = %s, image_height = %s, 
                            crop_mode = %s, processed = TRUE, updated_at = %s 
                        WHERE id = %s
                    """, (
                        orientation, 
                        dimensions[0], 
                        dimensions[1],
                        crop_mode_to_use,
                        datetime.now(),
                        slider_id
                    ))
        
        # Update data lainnya
        update_fields = []
        update_values = []
        
        if description is not None:
            update_fields.append("description = %s")
            update_values.append(description)
        
        if order_position is not None:
            update_fields.append("order_position = %s")
            update_values.append(order_position)
        
        if is_active is not None:
            update_fields.append("is_active = %s")
            update_values.append(is_active)
        
        if crop_mode is not None and not reprocess:
            update_fields.append("crop_mode = %s")
            update_values.append(crop_mode)
        
        update_fields.append("updated_at = %s")
        update_values.append(datetime.now())
        
        if update_fields:
            update_values.append(slider_id)
            update_query = f"""
                UPDATE event_slider 
                SET {', '.join(update_fields)} 
                WHERE id = %s
            """
            cursor.execute(update_query, update_values)
        
        connection.commit()
        
        # Ambil data terbaru
        cursor.execute("SELECT * FROM event_slider WHERE id = %s", (slider_id,))
        updated_slider = cursor.fetchone()
        updated_slider['url'] = f"http://localhost:8000/uploads/slider/{updated_slider['filename']}"
        
        return {
            "message": "Slider berhasil diupdate",
            "slider_id": slider_id,
            "slider": updated_slider,
            "reprocessed": reprocess
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/slider/{slider_id}/reprocess")
async def reprocess_slider_image(
    slider_id: int,
    crop_mode: str = Form("smart"),
    token: dict = Depends(verify_token)
):
    """Reproses gambar slider dengan mode crop berbeda (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah slider ada
        cursor.execute("SELECT * FROM event_slider WHERE id = %s", (slider_id,))
        slider = cursor.fetchone()
        
        if not slider:
            raise HTTPException(status_code=404, detail="Slider tidak ditemukan")
        
        file_path = os.path.join(SLIDER_UPLOAD_DIR, slider['filename'])
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File gambar tidak ditemukan")
        
        # Proses ulang gambar
        process_result = process_slider_image(file_path, crop_mode)
        
        if not process_result or process_result.get('action') == 'error':
            raise HTTPException(status_code=500, detail="Gagal memproses ulang gambar")
        
        # Update database
        orientation = detect_image_orientation(file_path)
        dimensions = get_image_dimensions(file_path)
        
        cursor.execute("""
            UPDATE event_slider 
            SET orientation = %s, image_width = %s, image_height = %s, 
                crop_mode = %s, processed = TRUE, updated_at = %s 
            WHERE id = %s
        """, (
            orientation, 
            dimensions[0], 
            dimensions[1],
            crop_mode,
            datetime.now(),
            slider_id
        ))
        
        connection.commit()
        
        return {
            "message": "Gambar berhasil diproses ulang",
            "slider_id": slider_id,
            "crop_mode": crop_mode,
            "orientation": orientation,
            "dimensions": {
                "width": dimensions[0],
                "height": dimensions[1]
            },
            "process_result": process_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error reprocessing slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error memproses ulang slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/slider/{slider_id}")
def delete_slider_image(
    slider_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus gambar slider (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil informasi file
        cursor.execute("SELECT filename FROM event_slider WHERE id = %s", (slider_id,))
        slider = cursor.fetchone()
        
        if not slider:
            raise HTTPException(status_code=404, detail="Slider tidak ditemukan")
        
        # Hapus file dari sistem
        file_path = os.path.join(SLIDER_UPLOAD_DIR, slider['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Error deleting file: {str(e)}")
        
        # Hapus dari database
        cursor.execute("DELETE FROM event_slider WHERE id = %s", (slider_id,))
        connection.commit()
        
        return {
            "message": "Slider berhasil dihapus"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/slider/public")
def get_public_slider():
    """Get gambar slider untuk public (tanpa auth)"""
    # Update struktur tabel jika diperlukan
    update_slider_table_structure()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM event_slider 
            WHERE is_active = TRUE 
            ORDER BY order_position ASC, created_at DESC
            LIMIT 5
        """)
        
        sliders = cursor.fetchall()
        
        # Tambahkan URL lengkap dan info untuk setiap gambar
        for slider in sliders:
            slider['url'] = f"http://localhost:8000/uploads/slider/{slider['filename']}"
            
            # Jika belum diproses, coba proses sekarang
            if not slider.get('processed') or not slider.get('orientation'):
                file_path = os.path.join(SLIDER_UPLOAD_DIR, slider['filename'])
                if os.path.exists(file_path):
                    try:
                        orientation = detect_image_orientation(file_path)
                        slider['orientation'] = orientation
                    except:
                        slider['orientation'] = 'unknown'
            else:
                slider['orientation'] = slider.get('orientation', 'unknown')
            
            # Tambahkan class CSS berdasarkan orientasi untuk frontend
            if slider['orientation'] == 'portrait':
                slider['css_class'] = 'slider-portrait'
                slider['object_fit'] = 'contain'
            elif slider['orientation'] == 'landscape':
                slider['css_class'] = 'slider-landscape'
                slider['object_fit'] = 'cover'
            else:
                slider['css_class'] = 'slider-default'
                slider['object_fit'] = 'cover'
        
        return sliders
        
    except Exception as e:
        logger.error(f"Error getting public slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/admin/slider/stats")
def get_slider_stats(token: dict = Depends(verify_token)):
    """Get statistik slider (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Total sliders
        cursor.execute("SELECT COUNT(*) as total FROM event_slider")
        total = cursor.fetchone()['total']
        
        # Active sliders
        cursor.execute("SELECT COUNT(*) as active FROM event_slider WHERE is_active = TRUE")
        active = cursor.fetchone()['active']
        
        # Inactive sliders
        cursor.execute("SELECT COUNT(*) as inactive FROM event_slider WHERE is_active = FALSE")
        inactive = cursor.fetchone()['inactive']
        
        # Sliders by orientation
        cursor.execute("""
            SELECT orientation, COUNT(*) as count 
            FROM event_slider 
            WHERE orientation IS NOT NULL 
            GROUP BY orientation
        """)
        orientation_stats = cursor.fetchall()
        
        # Processed vs unprocessed
        cursor.execute("SELECT COUNT(*) as processed FROM event_slider WHERE processed = TRUE")
        processed = cursor.fetchone()['processed']
        
        cursor.execute("SELECT COUNT(*) as unprocessed FROM event_slider WHERE processed = FALSE")
        unprocessed = cursor.fetchone()['unprocessed']
        
        return {
            "total_sliders": total,
            "active_sliders": active,
            "inactive_sliders": inactive,
            "orientation_stats": orientation_stats,
            "processed_sliders": processed,
            "unprocessed_sliders": unprocessed,
            "target_dimensions": {
                "width": SLIDER_TARGET_WIDTH,
                "height": SLIDER_TARGET_HEIGHT,
                "aspect_ratio": SLIDER_ASPECT_RATIO
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting slider stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil statistik slider: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ENDPOINT UNTUK TENTANG KAMI SLIDER (HERO IMAGES)
# ============================================

@router.get("/admin/tentang-kami/slider")
def get_tentang_kami_slider(token: dict = Depends(verify_token)):
    """Get semua gambar slider untuk Tentang Kami (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Update struktur tabel jika diperlukan
    update_tentang_kami_slider_structure()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM tentang_kami_slider 
            ORDER BY order_position ASC, created_at DESC
        """)
        
        sliders = cursor.fetchall()
        
        # Tambahkan URL dan info untuk setiap slider
        for slider in sliders:
            slider['url'] = f"http://localhost:8000/uploads/tentang_kami/{slider['filename']}"
            slider['aspect_ratio'] = SLIDER_ASPECT_RATIO
            slider['target_width'] = SLIDER_TARGET_WIDTH
            slider['target_height'] = SLIDER_TARGET_HEIGHT
            
            # Set default jika tidak ada
            if not slider.get('orientation'):
                slider['orientation'] = 'unknown'
            if not slider.get('crop_mode'):
                slider['crop_mode'] = 'smart'
        
        return sliders
        
    except Exception as e:
        logger.error(f"Error getting Tentang Kami slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil slider Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/admin/tentang-kami/slider")
async def upload_tentang_kami_slider(
    file: UploadFile = File(...),
    description: str = Form(None),
    order_position: int = Form(0),
    crop_mode: str = Form("smart"),
    token: dict = Depends(verify_token)
):
    """Upload gambar slider untuk Tentang Kami (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi file
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File harus berupa gambar")
    
    # Validasi ukuran file (max 10MB)
    file.file.seek(0, 2)  # Pindah ke akhir file
    file_size = file.file.tell()
    file.file.seek(0)  # Kembali ke awal file
    
    if file_size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB")
    
    # Validasi crop mode
    valid_crop_modes = ['smart', 'crop', 'fit', 'fill']
    if crop_mode not in valid_crop_modes:
        crop_mode = 'smart'
    
    # Generate nama file unik
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"tentang_kami_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{token['user_id']}.{file_extension}"
    
    # Simpan file
    file_path = os.path.join(TENTANG_KAMI_UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan file: {str(e)}")
    
    # Update struktur tabel
    update_tentang_kami_slider_structure()
    
    # Simpan ke database
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            INSERT INTO tentang_kami_slider 
            (filename, original_name, description, order_position, crop_mode)
            VALUES (%s, %s, %s, %s, %s)
        """, (unique_filename, file.filename, description, order_position, crop_mode))
        
        connection.commit()
        
        slider_id = cursor.lastrowid
        
        # Proses gambar sesuai crop mode
        process_result = process_slider_image(file_path, crop_mode)
        
        # Dapatkan dimensi dan orientasi setelah diproses
        orientation = detect_image_orientation(file_path)
        dimensions = get_image_dimensions(file_path)
        
        # Update database dengan info lengkap
        cursor.execute("""
            UPDATE tentang_kami_slider 
            SET orientation = %s, image_width = %s, image_height = %s, 
                processed = TRUE, updated_at = %s 
            WHERE id = %s
        """, (orientation, dimensions[0], dimensions[1], datetime.now(), slider_id))
        
        connection.commit()
        
        return {
            "message": "Gambar slider Tentang Kami berhasil diupload dan diproses",
            "slider_id": slider_id,
            "filename": unique_filename,
            "url": f"http://localhost:8000/uploads/tentang_kami/{unique_filename}",
            "orientation": orientation,
            "dimensions": {
                "width": dimensions[0],
                "height": dimensions[1]
            },
            "crop_mode": crop_mode,
            "process_result": process_result
        }
        
    except Exception as e:
        # Hapus file jika gagal menyimpan ke database
        if os.path.exists(file_path):
            os.remove(file_path)
        
        logger.error(f"Error saving to database: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan ke database: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/tentang-kami/slider/{slider_id}")
def delete_tentang_kami_slider(
    slider_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus gambar slider Tentang Kami (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil informasi file
        cursor.execute("SELECT filename FROM tentang_kami_slider WHERE id = %s", (slider_id,))
        slider = cursor.fetchone()
        
        if not slider:
            raise HTTPException(status_code=404, detail="Slider tidak ditemukan")
        
        # Hapus file dari sistem
        file_path = os.path.join(TENTANG_KAMI_UPLOAD_DIR, slider['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Error deleting file: {str(e)}")
        
        # Hapus dari database
        cursor.execute("DELETE FROM tentang_kami_slider WHERE id = %s", (slider_id,))
        connection.commit()
        
        return {
            "message": "Slider Tentang Kami berhasil dihapus"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting Tentang Kami slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus slider Tentang Kami: {str(e)}")
    finally:
        cursor.close()
        connection.close()