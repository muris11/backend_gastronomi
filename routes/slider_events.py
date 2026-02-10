# slider_events.py - VERSI DIPERBAIKI
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from dependencies.auth import verify_token
from config.database import db
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/slider-events", tags=["Slider Events"])

# Buat Pydantic model untuk request body
from pydantic import BaseModel

class SliderEventsRequest(BaseModel):
    selected_events: List[int]

# ============ ENDPOINT PUBLIC UNTUK USER ============
@router.get("/public")
def get_slider_events_public():
    """
    Endpoint public untuk mendapatkan slider events tanpa authentication
    Digunakan oleh frontend user (HomeUser.jsx)
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info("Fetching slider events for public access")
        
        # Cek apakah tabel ada
        cursor.execute("SHOW TABLES LIKE 'slider_events'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Buat tabel jika tidak ada
            cursor.execute("""
                CREATE TABLE slider_events (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    selected_events JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created slider_events table")
            connection.commit()
            
            # Insert default record
            cursor.execute("INSERT INTO slider_events (id, selected_events) VALUES (1, '[]')")
            connection.commit()
            logger.info("Created default slider events record")
            return {"selected_events": []}
        
        cursor.execute("SELECT selected_events FROM slider_events WHERE id = 1")
        result = cursor.fetchone()
        
        if not result:
            # Create default record dengan array kosong
            cursor.execute("INSERT INTO slider_events (id, selected_events) VALUES (1, '[]')")
            connection.commit()
            logger.info("Created default slider events record")
            return {"selected_events": []}
        
        # Parse JSON dari database
        selected_events = result['selected_events']
        if isinstance(selected_events, str):
            try:
                selected_events = json.loads(selected_events)
            except json.JSONDecodeError:
                selected_events = []
        
        # Pastikan selected_events adalah list of integers
        if not isinstance(selected_events, list):
            selected_events = []
        
        # Filter hanya event IDs yang valid
        valid_event_ids = []
        for event_id in selected_events:
            try:
                valid_event_ids.append(int(event_id))
            except (ValueError, TypeError):
                continue
        
        logger.info(f"Retrieved {len(valid_event_ids)} slider events for public access")
        return {"selected_events": valid_event_ids}
        
    except Exception as e:
        logger.error(f"Error getting slider events for public: {str(e)}", exc_info=True)
        # Return empty array instead of throwing error for public endpoint
        return {"selected_events": []}
    finally:
        cursor.close()
        connection.close()

# ============ ENDPOINT PROTECTED UNTUK ADMIN ============
@router.get("/")
def get_slider_events(token: str = Depends(verify_token)):
    """
    Endpoint protected untuk admin dengan authentication
    """
    connection = db.get_connection()
    cursor = connection.cursor(dictionary=True)
    
    try:
        logger.info("Fetching slider events for admin")
        
        # Cek apakah tabel ada
        cursor.execute("SHOW TABLES LIKE 'slider_events'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Buat tabel jika tidak ada
            cursor.execute("""
                CREATE TABLE slider_events (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    selected_events JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
            logger.info("Created slider_events table")
        
        cursor.execute("SELECT selected_events FROM slider_events WHERE id = 1")
        result = cursor.fetchone()
        
        if not result:
            # Create default record dengan array kosong
            cursor.execute("INSERT INTO slider_events (id, selected_events) VALUES (1, '[]')")
            connection.commit()
            logger.info("Created default slider events record")
            return {"selected_events": []}
        
        # Parse JSON dari database
        selected_events = result['selected_events']
        if isinstance(selected_events, str):
            try:
                selected_events = json.loads(selected_events)
            except json.JSONDecodeError:
                selected_events = []
        
        # Pastikan selected_events adalah list
        if not isinstance(selected_events, list):
            selected_events = []
        
        logger.info(f"Retrieved {len(selected_events)} slider events from database")
        return {"selected_events": selected_events}
        
    except Exception as e:
        logger.error(f"Error getting slider events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error mengambil data slider events: {str(e)}")
    finally:
        cursor.close()
        connection.close()

@router.post("/")
def save_slider_events(
    request: SliderEventsRequest,
    token: str = Depends(verify_token)
):
    connection = db.get_connection()
    cursor = connection.cursor()
    
    try:
        selected_events = request.selected_events
        logger.info(f"Received request to save slider events: {selected_events}")
        
        # Validasi input
        if not isinstance(selected_events, list):
            raise HTTPException(status_code=400, detail="selected_events harus berupa array")
        
        # Pastikan semua item adalah integers
        valid_events = []
        for event_id in selected_events:
            try:
                valid_events.append(int(event_id))
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Semua event ID harus berupa angka")
        
        # Convert to JSON string
        selected_events_json = json.dumps(valid_events)
        
        # Update atau insert record
        cursor.execute("""
            INSERT INTO slider_events (id, selected_events) 
            VALUES (1, %s)
            ON DUPLICATE KEY UPDATE selected_events = %s, updated_at = CURRENT_TIMESTAMP
        """, (selected_events_json, selected_events_json))
        
        connection.commit()
        logger.info(f"Successfully saved {len(valid_events)} slider events to database")
        
        return {
            "message": "Slider events berhasil disimpan",
            "selected_events": valid_events,
            "count": len(valid_events)
        }
        
    except Exception as e:
        logger.error(f"Error saving slider events: {str(e)}", exc_info=True)
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Error menyimpan slider events: {str(e)}")
    finally:
        cursor.close()
        connection.close()