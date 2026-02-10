from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
import logging
import os
import shutil
from PIL import Image
import io
import json
from fastapi import UploadFile, File, Form
from typing import List, Optional
from dependencies.auth import verify_token
from config.database import db
from utils.validators import check_foto_profil_column, delete_old_profile_picture

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin Stats"])

# Path untuk menyimpan file upload
SLIDER_UPLOAD_DIR = "uploads/slider"
TENTANG_KAMI_UPLOAD_DIR = "uploads/tentang_kami"
TIM_UPLOAD_DIR = "uploads/tim"
LAYANAN_UPLOAD_DIR = "uploads/layanan"  # ✅ DITAMBAHKAN

# Buat direktori jika belum ada
os.makedirs(SLIDER_UPLOAD_DIR, exist_ok=True)
os.makedirs(TENTANG_KAMI_UPLOAD_DIR, exist_ok=True)
os.makedirs(TIM_UPLOAD_DIR, exist_ok=True)
os.makedirs(LAYANAN_UPLOAD_DIR, exist_ok=True)  # ✅ DITAMBAHKAN

# Konfigurasi gambar
SLIDER_TARGET_WIDTH = 1200
SLIDER_TARGET_HEIGHT = 600
SLIDER_ASPECT_RATIO = SLIDER_TARGET_WIDTH / SLIDER_TARGET_HEIGHT
TIM_TARGET_WIDTH = 400
TIM_TARGET_HEIGHT = 400

# ============================================
# ✅ FUNGSI: Proses gambar tim
# ============================================

def process_tim_image(file_path: str) -> dict:
    """Proses gambar tim menjadi persegi 400x400"""
    try:
        with Image.open(file_path) as img:
            # Get original dimensions
            original_width, original_height = img.size
            
            # Convert ke RGB jika perlu
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Calculate cropping untuk buat persegi
            if original_width > original_height:
                # Landscape: crop width
                left = (original_width - original_height) // 2
                top = 0
                right = left + original_height
                bottom = original_height
            else:
                # Portrait: crop height
                left = 0
                top = (original_height - original_width) // 2
                right = original_width
                bottom = top + original_width
            
            # Crop gambar menjadi persegi
            img_cropped = img.crop((left, top, right, bottom))
            
            # Resize ke 400x400
            img_resized = img_cropped.resize((TIM_TARGET_WIDTH, TIM_TARGET_HEIGHT), Image.Resampling.LANCZOS)
            img_resized.save(file_path, quality=90, optimize=True)
            
            return {
                "success": True,
                "action": "cropped_and_resized",
                "original_size": (original_width, original_height),
                "crop_area": (left, top, right, bottom),
                "new_size": (TIM_TARGET_WIDTH, TIM_TARGET_HEIGHT)
            }
            
    except Exception as e:
        logger.error(f"Error processing tim image: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================
# ✅ FUNGSI BARU: Cek semua kolom sekaligus
# ============================================

def check_table_columns():
    """Cek semua kolom yang ada di tabel users"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("SHOW COLUMNS FROM users")
        columns = cursor.fetchall()
        column_names = [col['Field'] for col in columns]
        return column_names
    except Exception as e:
        logger.error(f"Error checking table columns: {str(e)}")
        return []
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ Update tabel database untuk menambahkan kolom orientasi
# ============================================

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

# ============================================
# ✅ Update tabel database untuk tentang_kami_slider
# ============================================

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
# ✅ FUNGSI: Buat tabel tentang_kami jika belum ada
# ============================================

def create_tentang_kami_table():
    """Buat tabel tentang_kami jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami (
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
        logger.info("✅ tentang_kami table ready")
    except Exception as e:
        logger.error(f"Error creating tentang_kami table: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ FUNGSI UNTUK MENGELOLA TABEL TIM
# ============================================

def create_tim_tables():
    """Buat tabel untuk tim jika belum ada"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Tabel anggota tim
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami_tim (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nama VARCHAR(100) NOT NULL,
                jabatan VARCHAR(100) NOT NULL,
                deskripsi TEXT,
                foto VARCHAR(255),
                urutan INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_urutan (urutan),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        # Tabel keahlian (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tentang_kami_tim_keahlian (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tim_id INT NOT NULL,
                keahlian VARCHAR(100) NOT NULL,
                urutan INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tim_id) REFERENCES tentang_kami_tim(id) ON DELETE CASCADE,
                INDEX idx_tim_id (tim_id),
                INDEX idx_urutan (urutan)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        
        connection.commit()
        logger.info("✅ Tabel tentang_kami_tim dan tentang_kami_tim_keahlian siap")
        
    except Exception as e:
        logger.error(f"Error creating tim tables: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ FUNGSI UNTUK MIGRASI DATA LAMA (OPSIONAL)
# ============================================

def migrate_old_tim_data():
    """Migrasi data tim dari JSON ke database (jalankan sekali)"""
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Cek apakah tabel tentang_kami ada
        cursor.execute("SHOW TABLES LIKE 'tentang_kami'")
        if not cursor.fetchone():
            logger.info("Tabel tentang_kami tidak ditemukan, skip migrasi")
            return
        
        # Cek apakah sudah ada data di tabel tim
        cursor.execute("SELECT COUNT(*) as count FROM tentang_kami_tim")
        if cursor.fetchone()['count'] > 0:
            logger.info("Data tim sudah ada, skip migrasi")
            return
        
        # Ambil data tim lama dari JSON
        cursor.execute("""
            SELECT content_value FROM tentang_kami 
            WHERE section = 'tim' AND section_key = 'members'
        """)
        
        old_data = cursor.fetchone()
        if not old_data or not old_data['content_value']:
            logger.info("Tidak ada data tim lama untuk dimigrasi")
            return
        
        try:
            members = json.loads(old_data['content_value'])
            logger.info(f"Found {len(members)} old tim members to migrate")
            
            for idx, member in enumerate(members):
                # Insert ke tabel baru
                cursor.execute("""
                    INSERT INTO tentang_kami_tim 
                    (nama, jabatan, deskripsi, urutan, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    member.get('name', ''),
                    member.get('position', ''),
                    member.get('description', ''),
                    idx,
                    True
                ))
                
                tim_id = cursor.lastrowid
                
                # Insert keahlian jika ada
                expertise = member.get('expertise', [])
                for skill_idx, skill in enumerate(expertise):
                    cursor.execute("""
                        INSERT INTO tentang_kami_tim_keahlian (tim_id, keahlian, urutan)
                        VALUES (%s, %s, %s)
                    """, (tim_id, skill, skill_idx))
            
            connection.commit()
            logger.info(f"✅ Successfully migrated {len(members)} tim members to database")
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing old tim data: {e}")
        except Exception as e:
            logger.error(f"Error during migration: {str(e)}")
            connection.rollback()
            
    except Exception as e:
        logger.error(f"Error migrating tim data: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# Jalankan migrasi saat module di-load
migrate_old_tim_data()

# ============================================
# ✅ ENDPOINT UNTUK STATISTIK ADMIN
# ============================================

@router.get("/admin/stats")
def get_admin_stats(token: dict = Depends(verify_token)):
    """Get statistik untuk admin dashboard"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Total users
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_users = cursor.fetchone()['total']
        
        # Active users (dengan login dalam 30 hari terakhir)
        cursor.execute("""
            SELECT COUNT(*) as active FROM users 
            WHERE last_login >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """)
        active_users = cursor.fetchone()['active']
        
        # New users hari ini
        cursor.execute("""
            SELECT COUNT(*) as new_today FROM users 
            WHERE DATE(created_at) = CURDATE()
        """)
        new_users_today = cursor.fetchone()['new_today']
        
        # Total orders
        cursor.execute("SELECT COUNT(*) as total FROM orders")
        total_orders = cursor.fetchone()['total']
        
        # Pending orders
        cursor.execute("SELECT COUNT(*) as pending FROM orders WHERE status = 'pending'")
        pending_orders = cursor.fetchone()['pending']
        
        # Completed orders
        cursor.execute("SELECT COUNT(*) as completed FROM orders WHERE status = 'completed'")
        completed_orders = cursor.fetchone()['completed']
        
        # Total revenue
        cursor.execute("SELECT SUM(total_amount) as revenue FROM orders WHERE status = 'completed'")
        revenue_result = cursor.fetchone()
        total_revenue = float(revenue_result['revenue']) if revenue_result['revenue'] else 0
        
        # Slider stats
        cursor.execute("SELECT COUNT(*) as total FROM event_slider")
        total_sliders = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM event_slider WHERE is_active = TRUE")
        active_sliders = cursor.fetchone()['active']
        
        # Tim stats
        cursor.execute("SELECT COUNT(*) as total FROM tentang_kami_tim")
        total_tim = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as active FROM tentang_kami_tim WHERE is_active = TRUE")
        active_tim = cursor.fetchone()['active']
        
        # System stats
        cursor.execute("SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema = DATABASE()")
        total_tables = cursor.fetchone()['total_tables']
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "new_today": new_users_today
            },
            "orders": {
                "total": total_orders,
                "pending": pending_orders,
                "completed": completed_orders,
                "revenue": total_revenue
            },
            "content": {
                "sliders": {
                    "total": total_sliders,
                    "active": active_sliders
                },
                "tim_members": {
                    "total": total_tim,
                    "active": active_tim
                }
            },
            "system": {
                "total_tables": total_tables,
                "server_time": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil statistik: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK BACKUP & RESTORE (SIMPLE)
# ============================================

@router.get("/admin/export/data")
def export_database_data(token: dict = Depends(verify_token)):
    """Export data database untuk backup (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Get all tables
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "tables": {}
        }
        
        for table in tables:
            table_name = list(table.values())[0]
            
            # Get table structure
            cursor.execute(f"DESCRIBE {table_name}")
            structure = cursor.fetchall()
            
            # Get table data
            cursor.execute(f"SELECT * FROM {table_name}")
            data = cursor.fetchall()
            
            export_data["tables"][table_name] = {
                "structure": structure,
                "data": data
            }
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengekspor data: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK SYSTEM HEALTH CHECK
# ============================================

@router.get("/admin/health")
def system_health_check(token: dict = Depends(verify_token)):
    """Check system health and database connection (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Database connection check
        cursor.execute("SELECT 1 as connection_check")
        db_check = cursor.fetchone()
        
        # Database version
        cursor.execute("SELECT VERSION() as version")
        db_version = cursor.fetchone()['version']
        
        # Check important tables
        important_tables = ['users', 'orders', 'event_slider', 'tentang_kami']
        table_status = {}
        
        for table in important_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                result = cursor.fetchone()
                table_status[table] = {
                    "exists": True,
                    "row_count": result['count']
                }
            except:
                table_status[table] = {
                    "exists": False,
                    "row_count": 0
                }
        
        # Disk usage (simple check)
        try:
            disk_usage = shutil.disk_usage(".")
            disk_info = {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent_used": round((disk_usage.used / disk_usage.total) * 100, 2)
            }
        except:
            disk_info = {"error": "Unable to get disk usage"}
        
        # Upload directories check
        upload_dirs = [SLIDER_UPLOAD_DIR, TENTANG_KAMI_UPLOAD_DIR, TIM_UPLOAD_DIR, LAYANAN_UPLOAD_DIR]
        dir_status = {}
        
        for dir_path in upload_dirs:
            dir_status[dir_path] = {
                "exists": os.path.exists(dir_path),
                "writable": os.access(dir_path, os.W_OK) if os.path.exists(dir_path) else False
            }
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": {
                "connection": "ok" if db_check else "failed",
                "version": db_version
            },
            "tables": table_status,
            "disk": disk_info,
            "directories": dir_status,
            "system": {
                "python_version": os.sys.version,
                "platform": os.sys.platform
            }
        }
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK LOGS VIEWER (SIMPLE)
# ============================================

@router.get("/admin/logs")
def get_recent_logs(
    lines: int = 100,
    token: dict = Depends(verify_token)
):
    """Get recent logs (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    try:
        # This is a simple log viewer that reads from the current log file
        log_file = "app.log"
        
        if not os.path.exists(log_file):
            return {
                "message": "Log file not found",
                "logs": []
            }
        
        # Read last N lines from log file
        with open(log_file, 'r', encoding='utf-8') as f:
            lines_content = f.readlines()[-lines:]
        
        # Parse logs
        parsed_logs = []
        for line in lines_content:
            line = line.strip()
            if not line:
                continue
            
            # Simple parsing (adjust based on your log format)
            if 'ERROR' in line:
                level = 'ERROR'
            elif 'WARNING' in line:
                level = 'WARNING'
            elif 'INFO' in line:
                level = 'INFO'
            else:
                level = 'DEBUG'
            
            parsed_logs.append({
                "level": level,
                "message": line,
                "timestamp": line[:23] if len(line) > 23 else "unknown"
            })
        
        return {
            "total_lines": len(lines_content),
            "logs": parsed_logs
        }
        
    except Exception as e:
        logger.error(f"Error reading logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error membaca logs: {str(e)}")

# ============================================
# ✅ ENDPOINT UNTUK CLEANUP
# ============================================

@router.post("/admin/cleanup")
def cleanup_system(
    cleanup_type: str = "temp",
    days_old: int = 7,
    token: dict = Depends(verify_token)
):
    """Cleanup system (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        cleanup_results = {
            "cleanup_type": cleanup_type,
            "timestamp": datetime.now().isoformat(),
            "deleted": {}
        }
        
        if cleanup_type == "temp" or cleanup_type == "all":
            # Cleanup old temporary uploads
            temp_dirs = [SLIDER_UPLOAD_DIR, TENTANG_KAMI_UPLOAD_DIR, TIM_UPLOAD_DIR, LAYANAN_UPLOAD_DIR]
            
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    deleted_files = []
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.isfile(file_path):
                            file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).days
                            if file_age_days > days_old:
                                try:
                                    os.remove(file_path)
                                    deleted_files.append(filename)
                                except Exception as e:
                                    logger.warning(f"Error deleting {filename}: {str(e)}")
                    
                    cleanup_results["deleted"][temp_dir] = {
                        "count": len(deleted_files),
                        "files": deleted_files[:10]  # Limit to 10 files
                    }
        
        if cleanup_type == "db" or cleanup_type == "all":
            # Cleanup old orders
            cursor.execute("""
                DELETE FROM orders 
                WHERE status = 'cancelled' 
                AND updated_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days_old * 2,))
            
            deleted_orders = cursor.rowcount
            cleanup_results["deleted"]["orders"] = {
                "count": deleted_orders,
                "type": "cancelled_orders_old"
            }
            
            connection.commit()
        
        return cleanup_results
        
    except Exception as e:
        connection.rollback()
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error melakukan cleanup: {str(e)}")
    finally:
        cursor.close()
        connection.close()

# ============================================
# ✅ ENDPOINT UNTUK SYSTEM INFO
# ============================================

@router.get("/admin/system/info")
def get_system_info(token: dict = Depends(verify_token)):
    """Get system information (admin only)"""
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="Akses ditolak")
    
    try:
        import platform
        import psutil
        
        # System info
        system_info = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "architecture": platform.architecture()[0]
        }
        
        # CPU info
        cpu_info = {
            "cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "usage_percent": psutil.cpu_percent(interval=1)
        }
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent_used": memory.percent
        }
        
        # Disk info
        disk = psutil.disk_usage('.')
        disk_info = {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": disk.percent
        }
        
        # Process info
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "name": process.name(),
            "memory_percent": round(process.memory_percent(), 2),
            "cpu_percent": process.cpu_percent(interval=1)
        }
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": system_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "process": process_info
        }
        
    except ImportError:
        # If psutil is not installed
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "note": "psutil not installed for detailed metrics"
            }
        }
    except Exception as e:
        logger.error(f"Error getting system info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error mengambil informasi sistem: {str(e)}")