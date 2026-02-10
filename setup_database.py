# setup_database.py
import mysql.connector
from mysql.connector import Error
import os

def setup_database():
    try:
        # Koneksi ke MySQL (tanpa database)
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',  # Sesuaikan dengan password MySQL Anda
            port=3306
        )
        
        cursor = connection.cursor()
        
        # Buat database jika belum ada
        cursor.execute("CREATE DATABASE IF NOT EXISTS inventory_db")
        cursor.execute("USE inventory_db")
        
        print("✅ Database inventory_db berhasil dibuat/ditemukan")
        
        # Baca dan eksekusi file SQL
        with open('database_schema.sql', 'r', encoding='utf-8') as file:
            sql_script = file.read()
        
        # Eksekusi perintah SQL satu per satu
        commands = sql_script.split(';')
        for command in commands:
            command = command.strip()
            if command:
                try:
                    cursor.execute(command)
                    print(f"✅ Executed: {command[:50]}...")
                except Error as e:
                    print(f"⚠️  Warning: {e}")
        
        connection.commit()
        print("✅ Semua tabel berhasil dibuat!")
        
        # Test data insertion
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Jumlah user: {user_count}")
        
        cursor.execute("SELECT COUNT(*) FROM categories")
        category_count = cursor.fetchone()[0]
        print(f"✅ Jumlah kategori: {category_count}")
        
        cursor.execute("SELECT COUNT(*) FROM items")
        item_count = cursor.fetchone()[0]
        print(f"✅ Jumlah barang: {item_count}")
        
    except Error as e:
        print(f"❌ Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("✅ Koneksi database ditutup")

if __name__ == "__main__":
    setup_database()