import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

class Database:
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', ''),
            'database': os.getenv('DB_NAME', 'inventory_db'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'charset': 'utf8mb4',
            'autocommit': False
        }
    
    def get_connection(self):
        try:
            connection = mysql.connector.connect(**self.config)
            return connection
        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            raise Exception("Database connection failed")

db = Database()