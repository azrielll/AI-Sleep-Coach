import sqlite3
import os
import sys
from werkzeug.security import generate_password_hash

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.getenv('DATABASE_PATH', 'database.db')
DATABASE = os.path.join(BASE_DIR, DATABASE_NAME) if not os.path.isabs(DATABASE_NAME) else DATABASE_NAME

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure tables are created first by importing app
import app

def create_admin(email, password, nama):
    try:
        with get_db() as conn:
            pwd_hash = generate_password_hash(password)
            conn.execute(
                'INSERT INTO users (nama, email, password_hash, role) VALUES (?, ?, ?, ?)',
                (nama, email, pwd_hash, 'admin')
            )
        print(f"Akun admin berhasil dibuat:\nEmail: {email}\nNama: {nama}")
    except sqlite3.IntegrityError:
        print(f"Error: Email {email} sudah terdaftar di database.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Penggunaan: python create_admin.py <email> <password> \"<nama_lengkap>\"")
        print("Contoh: python create_admin.py admin@sleepcoach.com pass123 \"Admin Utama\"")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    nama = sys.argv[3]
    
    create_admin(email, password, nama)
