import json
import mysql.connector
from datetime import datetime

def migrate_data():
    # Koneksi database
    conn = mysql.connector.connect(
        host='localhost',
        user='your_username',
        password='your_password',
        database='inventory_db'
    )
    cursor = conn.cursor(dictionary=True)
    
    # Migrasi kategori
    try:
        with open('kategori.json', 'r', encoding='utf-8') as f:
            categories = json.load(f)
            
        for cat in categories:
            if isinstance(cat, dict):
                category_name = cat.get('nama')
            else:
                category_name = cat
                
            cursor.execute("INSERT IGNORE INTO categories (nama) VALUES (%s)", (category_name,))
        
        conn.commit()
        print("Kategori migrated successfully")
    except FileNotFoundError:
        print("kategori.json not found, skipping...")
    
    # Migrasi barang
    try:
        with open('barang.json', 'r', encoding='utf-8') as f:
            items = json.load(f)
            
        for item in items:
            # Get kategori_id
            cursor.execute("SELECT id FROM categories WHERE nama = %s", (item['kategori'],))
            kategori_result = cursor.fetchone()
            if not kategori_result:
                cursor.execute("INSERT INTO categories (nama) VALUES (%s)", (item['kategori'],))
                kategori_id = cursor.lastrowid
            else:
                kategori_id = kategori_result['id']
            
            # Insert item
            cursor.execute("""
                INSERT INTO items (id, nama_barang, kategori_id, tahun_perolehan, deskripsi, foto)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (item['id'], item['nama_barang'], kategori_id, item.get('tahun_perolehan', 2025), 
                  item.get('deskripsi', ''), item.get('foto')))
            
            # Insert stock units
            for unit in item.get('stok', []):
                cursor.execute("""
                    INSERT INTO stock_units (barang_id, kode, kondisi, status)
                    VALUES (%s, %s, %s, %s)
                """, (item['id'], unit['kode'], unit.get('kondisi', 'Baik'), unit.get('status', 'Tersedia')))
        
        conn.commit()
        print("Barang migrated successfully")
    except FileNotFoundError:
        print("barang.json not found, skipping...")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    migrate_data()