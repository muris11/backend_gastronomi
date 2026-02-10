from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from datetime import datetime
import logging
import os
import shutil
import json
from typing import Optional
from PIL import Image
from dependencies.auth import verify_token
from config.database import db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Layanan"])

# Path untuk menyimpan file upload
LAYANAN_UPLOAD_DIR = "uploads/layanan"

# Buat direktori jika belum ada
os.makedirs(LAYANAN_UPLOAD_DIR, exist_ok=True)

# Konfigurasi gambar
SLIDER_TARGET_WIDTH = 1200
SLIDER_TARGET_HEIGHT = 600
SLIDER_ASPECT_RATIO = SLIDER_TARGET_WIDTH / SLIDER_TARGET_HEIGHT

# ============================================
# ✅ FUNGSI: Deteksi orientasi gambar
# ============================================

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

# ============================================
# ✅ FUNGSI: Get dimensi gambar
# ============================================

def get_image_dimensions(image_path: str):
    """Get dimensi gambar (width, height)"""
    try:
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except Exception as e:
        logger.error(f"Error getting image dimensions: {str(e)}")
        return (0, 0)

# ============================================
# ✅ FUNGSI: Auto-crop gambar ke aspect ratio slider
# ============================================

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

# ============================================
# ✅ FUNGSI: Proses gambar dengan smart cropping
# ============================================

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

# ============================================
# ✅ FUNGSI: Buat tabel layanan jika belum ada
# ============================================

def create_layanan_table():
    """Buat tabel layanan jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS layanan (
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
        logger.info("✅ layanan table ready")
    except Exception as e:
        logger.error(f"Error creating layanan table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ FUNGSI: Buat tabel layanan_slider jika belum ada
# ============================================

def create_layanan_slider_table():
    """Buat tabel layanan_slider jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS layanan_slider (
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
        logger.info("✅ layanan_slider table ready")
    except Exception as e:
        logger.error(f"Error creating layanan_slider table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK LAYANAN (CRUD) - MENGGUNAKAN DATABASE
# ============================================

@router.get("/admin/layanan")
def get_layanan_content(token: dict = Depends(verify_token)):
    """Get semua konten Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_layanan_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM layanan ORDER BY section, section_key")
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
                    result[section][key] = json.loads(content_value) if content_value else []
                except:
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend (sesuai dengan LayananKamiAdmin.jsx)
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', 'LAYANAN KAMI'),
            "hero_subtitle": result.get('hero', {}).get('subtitle', 'Solusi Lengkap untuk Pengalaman Lari Terbaik'),
            "hero_description": result.get('hero', {}).get('description', 'Dari event organization hingga community building, kami menyediakan semua yang Anda butuhkan untuk pengalaman lari yang tak terlupakan.'),
            "services": result.get('services', {}).get('items', [
                {
                    "icon": "Activity",
                    "title": "Event Organization",
                    "description": "Menyelenggarakan berbagai jenis event lari dengan rute yang menarik melalui kota-kota besar Indonesia.",
                    "features": ["Rute terukur & aman", "Pendaftaran online", "Tim medis standby"]
                },
                {
                    "icon": "Utensils",
                    "title": "Culinary Experience",
                    "description": "Mengintegrasikan pengalaman kuliner lokal dalam setiap event untuk memperkaya petualangan peserta.",
                    "features": ["Food tasting", "Local cuisine", "Nutrition guidance"]
                },
                {
                    "icon": "Trophy",
                    "title": "Race Package",
                    "description": "Paket lengkap termasuk jersey, medali finisher, timing chip, dan souvenir eksklusif.",
                    "features": ["Quality merchandise", "Finisher medal", "Digital certificate"]
                },
                {
                    "icon": "Users",
                    "title": "Community Building",
                    "description": "Membangun komunitas pelari yang solid dengan regular training sessions dan gathering.",
                    "features": ["Weekly runs", "Training programs", "Social events"]
                }
            ]),
            "target_audience": result.get('target_audience', {}).get('items', [
                {
                    "title": "Untuk Pelari",
                    "icon": "Users",
                    "description": "Kami menyediakan event lari berkualitas dengan rute yang menarik, sistem pendaftaran yang mudah, dan pengalaman yang memuaskan. Setiap event dirancang untuk memberikan pengalaman terbaik bagi pelari dari berbagai level.",
                    "features": ["Event berkualitas", "Rute menarik", "Pendaftaran mudah", "Pengalaman memuaskan"]
                },
                {
                    "title": "Untuk Event Organizer & Brand",
                    "icon": "Award",
                    "description": "Kami adalah partner terpercaya untuk menyelenggarakan event lari yang tepat sasaran dengan desain yang kreatif dan profesional. Kami membantu brand dan event organizer meningkatkan reach mereka melalui platform dan jaringan yang luas.",
                    "features": ["Partner terpercaya", "Desain kreatif", "Platform luas", "Jaringan kuat"]
                }
            ]),
            "kontak_info": result.get('kontak', {}).get('info', {
                "email": "info@gastronomirun.com",
                "phone": "(021) 1234-5678",
                "address": "Jakarta Running Center, Indonesia",
                "social_media": {
                    "facebook": "https://facebook.com/gastronomirun",
                    "instagram": "https://instagram.com/gastronomirun",
                    "twitter": "https://twitter.com/gastronomirun",
                    "youtube": "https://youtube.com/gastronomirun"
                }
            })
        }
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting Layanan content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil konten Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.put("/admin/layanan")
async def update_layanan_content(
    request: dict,
    token: dict = Depends(verify_token)
):
    """Update konten Layanan (admin only)"""
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
        create_layanan_table()
        
        # Mapping untuk setiap section yang bisa diupdate
        section_mapping = {
            'hero': [
                ('title', 'text', data.get('hero_title', '')),
                ('subtitle', 'text', data.get('hero_subtitle', '')),
                ('description', 'text', data.get('hero_description', ''))
            ],
            'services': [
                ('items', 'array', json.dumps(data.get('services', [])))
            ],
            'target_audience': [
                ('items', 'array', json.dumps(data.get('target_audience', [])))
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
                    SELECT id FROM layanan 
                    WHERE section = %s AND section_key = %s
                """, (section, key))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing
                    cursor.execute("""
                        UPDATE layanan 
                        SET content_type = %s, content_value = %s, updated_at = %s
                        WHERE section = %s AND section_key = %s
                    """, (content_type, content_value, datetime.now(), section, key))
                else:
                    # Insert new
                    cursor.execute("""
                        INSERT INTO layanan (section, section_key, content_type, content_value)
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
        logger.error(f"Error updating Layanan content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengupdate konten Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.delete("/admin/layanan/reset")
def reset_layanan_content(
    section: Optional[str] = None,
    token: dict = Depends(verify_token)
):
    """Reset konten Layanan ke default (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_layanan_table()
        
        if section:
            # Reset specific section
            cursor.execute("DELETE FROM layanan WHERE section = %s", (section,))
            message = f"Data {section} berhasil direset ke default"
        else:
            # Reset all
            cursor.execute("DELETE FROM layanan")
            message = "Semua data Layanan berhasil direset ke default"
        
        connection.commit()
        
        return {
            "message": message,
            "reset_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting Layanan content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mereset konten Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.get("/layanan/public")
def get_public_layanan():
    """Get konten Layanan untuk public (tanpa auth)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Buat tabel jika belum ada
        create_layanan_table()
        
        # Ambil semua data dari database
        cursor.execute("SELECT * FROM layanan ORDER BY section, section_key")
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
                    result[section][key] = json.loads(content_value) if content_value else []
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {section}.{key}: {e}")
                    result[section][key] = content_value
            else:
                result[section][key] = content_value
        
        # Format khusus untuk frontend
        formatted_result = {
            "hero_title": result.get('hero', {}).get('title', 'LAYANAN KAMI'),
            "hero_subtitle": result.get('hero', {}).get('subtitle', 'Solusi Lengkap untuk Pengalaman Lari Terbaik'),
            "hero_description": result.get('hero', {}).get('description', 'Dari event organization hingga community building, kami menyediakan semua yang Anda butuhkan untuk pengalaman lari yang tak terlupakan.'),
            "services": result.get('services', {}).get('items', [
                {
                    "icon": "Activity",
                    "title": "Event Organization",
                    "description": "Menyelenggarakan berbagai jenis event lari dengan rute yang menarik melalui kota-kota besar Indonesia.",
                    "features": ["Rute terukur & aman", "Pendaftaran online", "Tim medis standby"]
                },
                {
                    "icon": "Utensils",
                    "title": "Culinary Experience",
                    "description": "Mengintegrasikan pengalaman kuliner lokal dalam setiap event untuk memperkaya petualangan peserta.",
                    "features": ["Food tasting", "Local cuisine", "Nutrition guidance"]
                },
                {
                    "icon": "Trophy",
                    "title": "Race Package",
                    "description": "Paket lengkap termasuk jersey, medali finisher, timing chip, dan souvenir eksklusif.",
                    "features": ["Quality merchandise", "Finisher medal", "Digital certificate"]
                },
                {
                    "icon": "Users",
                    "title": "Community Building",
                    "description": "Membangun komunitas pelari yang solid dengan regular training sessions dan gathering.",
                    "features": ["Weekly runs", "Training programs", "Social events"]
                }
            ]),
            "target_audience": result.get('target_audience', {}).get('items', [
                {
                    "title": "Untuk Pelari",
                    "icon": "Users",
                    "description": "Kami menyediakan event lari berkualitas dengan rute yang menarik, sistem pendaftaran yang mudah, dan pengalaman yang memuaskan. Setiap event dirancang untuk memberikan pengalaman terbaik bagi pelari dari berbagai level.",
                    "features": ["Event berkualitas", "Rute menarik", "Pendaftaran mudah", "Pengalaman memuaskan"]
                },
                {
                    "title": "Untuk Event Organizer & Brand",
                    "icon": "Award",
                    "description": "Kami adalah partner terpercaya untuk menyelenggarakan event lari yang tepat sasaran dengan desain yang kreatif dan profesional. Kami membantu brand dan event organizer meningkatkan reach mereka melalui platform dan jaringan yang luas.",
                    "features": ["Partner terpercaya", "Desain kreatif", "Platform luas", "Jaringan kuat"]
                }
            ]),
            "kontak_info": result.get('kontak', {}).get('info', {
                "email": "info@gastronomirun.com",
                "phone": "(021) 1234-5678",
                "address": "Jakarta Running Center, Indonesia",
                "social_media": {
                    "facebook": "https://facebook.com/gastronomirun",
                    "instagram": "https://instagram.com/gastronomirun",
                    "twitter": "https://twitter.com/gastronomirun",
                    "youtube": "https://youtube.com/gastronomirun"
                }
            })
        }
        
        return formatted_result
        
    except Exception as e:
        logger.error(f"Error getting public Layanan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil data Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK LAYANAN SLIDER (HERO IMAGES)
# ============================================

@router.get("/admin/layanan/slider")
def get_layanan_slider(token: dict = Depends(verify_token)):
    """Get semua gambar slider untuk Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    create_layanan_slider_table()
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM layanan_slider 
            ORDER BY order_position ASC, created_at DESC
        """)
        
        sliders = cursor.fetchall()
        
        # Tambahkan URL dan info untuk setiap slider
        for slider in sliders:
            slider['url'] = f"http://localhost:8000/uploads/layanan/{slider['filename']}"
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
        logger.error(f"Error getting Layanan slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil slider Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/admin/layanan/slider")
async def upload_layanan_slider(
    file: UploadFile = File(...),
    description: str = Form(None),
    order_position: int = Form(0),
    crop_mode: str = Form("smart"),
    token: dict = Depends(verify_token)
):
    """Upload gambar slider untuk Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    # Validasi file
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File harus berupa gambar")
    
    # Validasi ukuran file (max 10MB)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB")
    
    # Validasi crop mode
    valid_crop_modes = ['smart', 'crop', 'fit', 'fill']
    if crop_mode not in valid_crop_modes:
        crop_mode = 'smart'
    
    # Generate nama file unik
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"layanan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}.{file_extension}"
    
    # Simpan file
    file_path = os.path.join(LAYANAN_UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menyimpan file: {str(e)}")
    
    create_layanan_slider_table()
    
    # Simpan ke database
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            INSERT INTO layanan_slider 
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
            UPDATE layanan_slider 
            SET orientation = %s, image_width = %s, image_height = %s, 
                processed = TRUE, updated_at = %s 
            WHERE id = %s
        """, (orientation, dimensions[0], dimensions[1], datetime.now(), slider_id))
        
        connection.commit()
        
        return {
            "message": "Gambar slider Layanan berhasil diupload dan diproses",
            "slider_id": slider_id,
            "filename": unique_filename,
            "url": f"http://localhost:8000/uploads/layanan/{unique_filename}",
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

@router.delete("/admin/layanan/slider/{slider_id}")
def delete_layanan_slider(
    slider_id: int,
    token: dict = Depends(verify_token)
):
    """Hapus gambar slider Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Ambil informasi file
        cursor.execute("SELECT filename FROM layanan_slider WHERE id = %s", (slider_id,))
        slider = cursor.fetchone()
        
        if not slider:
            raise HTTPException(status_code=404, detail="Slider tidak ditemukan")
        
        # Hapus file dari sistem
        file_path = os.path.join(LAYANAN_UPLOAD_DIR, slider['filename'])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Error deleting file: {str(e)}")
        
        # Hapus dari database
        cursor.execute("DELETE FROM layanan_slider WHERE id = %s", (slider_id,))
        connection.commit()
        
        return {
            "message": "Slider Layanan berhasil dihapus"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error deleting Layanan slider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error menghapus slider Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK LAYANAN STATS
# ============================================

@router.get("/admin/layanan/stats")
def get_layanan_stats(token: dict = Depends(verify_token)):
    """Get statistik untuk halaman Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Pastikan tabel ada
        create_layanan_table()
        create_layanan_slider_table()
        
        # Statistik konten Layanan
        cursor.execute("SELECT COUNT(*) as total FROM layanan")
        total_content = cursor.fetchone()['total']
        
        # Statistik slider Layanan
        cursor.execute("SELECT COUNT(*) as total FROM layanan_slider")
        total_sliders = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM layanan_slider WHERE is_active = TRUE")
        active_sliders = cursor.fetchone()['active']
        
        # Statistik berdasarkan section
        cursor.execute("""
            SELECT section, COUNT(*) as count 
            FROM layanan 
            GROUP BY section
        """)
        sections = cursor.fetchall()
        
        # Default data check
        has_hero_data = False
        has_services_data = False
        has_target_audience_data = False
        has_kontak_data = False
        
        cursor.execute("SELECT COUNT(*) as count FROM layanan WHERE section = 'hero'")
        if cursor.fetchone()['count'] > 0:
            has_hero_data = True
        
        cursor.execute("SELECT COUNT(*) as count FROM layanan WHERE section = 'services'")
        if cursor.fetchone()['count'] > 0:
            has_services_data = True
        
        cursor.execute("SELECT COUNT(*) as count FROM layanan WHERE section = 'target_audience'")
        if cursor.fetchone()['count'] > 0:
            has_target_audience_data = True
        
        cursor.execute("SELECT COUNT(*) as count FROM layanan WHERE section = 'kontak'")
        if cursor.fetchone()['count'] > 0:
            has_kontak_data = True
        
        return {
            "content": {
                "total_items": total_content,
                "sections": sections,
                "has_hero_data": has_hero_data,
                "has_services_data": has_services_data,
                "has_target_audience_data": has_target_audience_data,
                "has_kontak_data": has_kontak_data
            },
            "sliders": {
                "total": total_sliders,
                "active": active_sliders,
                "inactive": total_sliders - active_sliders
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting Layanan stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil statistik Layanan: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK BULK OPERATIONS LAYANAN
# ============================================

@router.post("/admin/layanan/bulk")
async def bulk_operations_layanan(
    operation: str,
    data: Optional[dict] = None,
    token: dict = Depends(verify_token)
):
    """Bulk operations untuk Layanan (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        create_layanan_table()
        
        if operation == "export":
            # Export semua data layanan
            cursor.execute("SELECT * FROM layanan ORDER BY section, section_key")
            rows = cursor.fetchall()
            
            return {
                "operation": "export",
                "count": len(rows),
                "data": rows,
                "exported_at": datetime.now().isoformat()
            }
        
        elif operation == "import" and data:
            # Import data ke layanan
            imported_count = 0
            skipped_count = 0
            
            for item in data.get('data', []):
                try:
                    # Cek apakah data sudah ada
                    cursor.execute("""
                        SELECT id FROM layanan 
                        WHERE section = %s AND section_key = %s
                    """, (item['section'], item['section_key']))
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Update existing
                        cursor.execute("""
                            UPDATE layanan 
                            SET content_type = %s, content_value = %s, updated_at = %s
                            WHERE id = %s
                        """, (item['content_type'], item['content_value'], datetime.now(), existing['id']))
                    else:
                        # Insert new
                        cursor.execute("""
                            INSERT INTO layanan (section, section_key, content_type, content_value)
                            VALUES (%s, %s, %s, %s)
                        """, (item['section'], item['section_key'], item['content_type'], item['content_value']))
                    
                    imported_count += 1
                except Exception as e:
                    logger.warning(f"Error importing item: {str(e)}")
                    skipped_count += 1
            
            connection.commit()
            
            return {
                "operation": "import",
                "imported": imported_count,
                "skipped": skipped_count,
                "imported_at": datetime.now().isoformat()
            }
        
        elif operation == "validate":
            # Validasi struktur data layanan
            validation_results = {
                "tables_exist": {
                    "layanan": False,
                    "layanan_slider": False
                },
                "required_data": {
                    "hero": False,
                    "services": False,
                    "target_audience": False,
                    "kontak": False
                }
            }
            
            # Check tables
            cursor.execute("SHOW TABLES LIKE 'layanan'")
            validation_results["tables_exist"]["layanan"] = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'layanan_slider'")
            validation_results["tables_exist"]["layanan_slider"] = cursor.fetchone() is not None
            
            # Check required data
            required_sections = ['hero', 'services', 'target_audience', 'kontak']
            for section in required_sections:
                cursor.execute("SELECT COUNT(*) as count FROM layanan WHERE section = %s", (section,))
                validation_results["required_data"][section] = cursor.fetchone()['count'] > 0
            
            validation_results["is_valid"] = (
                validation_results["tables_exist"]["layanan"] and
                all(validation_results["required_data"].values())
            )
            
            return {
                "operation": "validate",
                "results": validation_results,
                "validated_at": datetime.now().isoformat()
            }
        
        else:
            raise HTTPException(status_code=400, detail="Operation tidak valid atau data tidak diberikan")
        
    except HTTPException:
        raise
    except Exception as e:
        connection.rollback()
        logger.error(f"Error in bulk operation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error dalam operasi bulk: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Panggil saat module di-load untuk buat tabel
create_layanan_table()
create_layanan_slider_table()