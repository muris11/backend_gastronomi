import mysql.connector
from mysql.connector import Error

def create_database():
    try:
        connection = mysql.connector.connect(
            host="localhost",
            user="your_username",
            password="your_password"
        )
        
        cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS inventory_db")
        print("Database created successfully")
        
    except Error as e:
        print(f"Error creating database: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == "__main__":
    create_database()