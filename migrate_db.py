import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def migrate():
    print(f"Memulai migrasi database di {DATABASE}...")
    try:
        with get_db() as conn:
            print("1. Menambahkan kolom 'role' ke tabel 'users'...")
            try:
                conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'pasien'")
                print("   Kolom 'role' berhasil ditambahkan.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print("   Kolom 'role' sudah ada, dilewati.")
                else:
                    raise e

            print("2. Migrasi tabel 'daily_logs' (mengubah user_id menjadi patient_id)...")
            try:
                conn.executescript('''
                    CREATE TABLE IF NOT EXISTS daily_logs_new (
                        id               INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id       INTEGER NOT NULL,
                        tanggal          TEXT    NOT NULL,
                        jam_mulai_tidur  TEXT    NOT NULL,
                        jam_bangun       TEXT    NOT NULL,
                        tingkat_stres    INTEGER NOT NULL,
                        konsumsi_kafein  INTEGER NOT NULL,
                        durasi_olahraga  INTEGER NOT NULL,
                        durasi_layar     INTEGER NOT NULL,
                        sleep_score      REAL    NOT NULL,
                        kategori         TEXT    NOT NULL,
                        FOREIGN KEY (patient_id) REFERENCES users(id)
                    );
                ''')
                # Check if old daily_logs table has user_id
                cols = [c[1] for c in conn.execute("PRAGMA table_info(daily_logs)").fetchall()]
                if 'user_id' in cols:
                    conn.executescript('''
                        INSERT INTO daily_logs_new (id, patient_id, tanggal, jam_mulai_tidur, jam_bangun, tingkat_stres, konsumsi_kafein, durasi_olahraga, durasi_layar, sleep_score, kategori)
                        SELECT id, user_id, tanggal, jam_mulai_tidur, jam_bangun, tingkat_stres, konsumsi_kafein, durasi_olahraga, durasi_layar, sleep_score, kategori FROM daily_logs;
                        DROP TABLE daily_logs;
                        ALTER TABLE daily_logs_new RENAME TO daily_logs;
                    ''')
                    print("   Migrasi tabel 'daily_logs' selesai.")
                else:
                    print("   Tabel 'daily_logs' sudah menggunakan patient_id, dilewati.")
            except Exception as e:
                print(f"   Note/Skip daily_logs migration: {e}")

            print("3. Menambahkan kolom 'created_by_admin_id' dan 'catatan_admin' ke tabel 'analisis_awal'...")
            cols = [c[1] for c in conn.execute("PRAGMA table_info(analisis_awal)").fetchall()]
            if 'created_by_admin_id' not in cols:
                conn.execute("ALTER TABLE analisis_awal ADD COLUMN created_by_admin_id INTEGER REFERENCES users(id)")
                print("   Kolom 'created_by_admin_id' berhasil ditambahkan.")
            else:
                print("   Kolom 'created_by_admin_id' sudah ada, dilewati.")

            if 'catatan_admin' not in cols:
                conn.execute("ALTER TABLE analisis_awal ADD COLUMN catatan_admin TEXT")
                print("   Kolom 'catatan_admin' berhasil ditambahkan.")
            else:
                print("   Kolom 'catatan_admin' sudah ada, dilewati.")

        print("Migrasi selesai dengan sukses!")
    except Exception as e:
        print(f"Terjadi kesalahan saat migrasi: {e}")

if __name__ == '__main__':
    migrate()
