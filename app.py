import os
import json
import sqlite3
import numpy as np
import joblib
import shap
import warnings
from datetime import datetime, date, time, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import google.generativeai as genai

import re
from markupsafe import Markup

warnings.filterwarnings('ignore')
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'sleepcoach-secret-2024')
app.jinja_env.filters['fromjson'] = json.loads

def render_markdown(text):
    if not text:
        return ''
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong style="color:var(--text-primary); font-weight:700; display:inline-block; margin-top:0.5rem;">\1</strong>', text)
    return Markup(text)

app.jinja_env.filters['render_markdown'] = render_markdown

# ── Gemini ──────────────────────────────────────────────────────────────────
genai.configure(api_key=os.getenv('GEMINI_API_KEY', ''))
gemini_model = genai.GenerativeModel('gemini-flash-latest')

# ── ML Models ────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models')

rf_model      = joblib.load(os.path.join(MODELS_DIR, 'random_forest_sleep_disorder.joblib'))
le_gender     = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_gender.joblib'))
le_bmi        = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_bmi.joblib'))
le_occupation = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_occupation.joblib'))
le_target     = joblib.load(os.path.join(MODELS_DIR, 'label_encoder_target.joblib'))

FEATURE_COLUMNS = [
    'Gender', 'Age', 'Occupation', 'Sleep Duration', 'Quality of Sleep',
    'Physical Activity Level', 'Stress Level', 'BMI Category',
    'Heart Rate', 'Daily Steps', 'Systolic', 'Diastolic'
]

OCCUPATIONS   = list(le_occupation.classes_)
DATABASE_NAME = os.getenv('DATABASE_PATH', 'database.db')
DATABASE      = os.path.join(BASE_DIR, DATABASE_NAME) if not os.path.isabs(DATABASE_NAME) else DATABASE_NAME

# ── Database ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nama         TEXT    NOT NULL,
                email        TEXT    NOT NULL UNIQUE,
                password_hash TEXT   NOT NULL,
                role         TEXT    DEFAULT 'pasien',
                created_at   TEXT    DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS daily_logs (
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
            CREATE TABLE IF NOT EXISTS analisis_awal (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id          INTEGER NOT NULL,
                created_by_admin_id INTEGER,
                tanggal             TEXT    NOT NULL,
                input_data_json     TEXT    NOT NULL,
                hasil_prediksi      TEXT    NOT NULL,
                probabilitas_json   TEXT    NOT NULL,
                shap_values_json    TEXT    NOT NULL,
                penjelasan_gemini   TEXT,
                catatan_admin       TEXT,
                FOREIGN KEY (patient_id) REFERENCES users(id),
                FOREIGN KEY (created_by_admin_id) REFERENCES users(id)
            );
        ''')

init_db()

# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                abort(403)
            if 'patient_id' in kwargs and session.get('role') == 'pasien':
                if session.get('user_id') != kwargs['patient_id']:
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.errorhandler(403)
def forbidden_error(e):
    flash('Anda tidak memiliki akses ke halaman ini (403 Forbidden).', 'error')
    if session.get('role') == 'admin':
        return redirect(url_for('admin_dashboard')), 403
    elif session.get('role') == 'pasien':
        return redirect(url_for('dashboard')), 403
    return redirect(url_for('login')), 403

# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nama     = request.form.get('nama', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if not nama or not email or not password:
            flash('Semua field wajib diisi.', 'error')
            return render_template('register.html')
        if password != confirm:
            flash('Password tidak cocok.', 'error')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password minimal 6 karakter.', 'error')
            return render_template('register.html')
        pwd_hash = generate_password_hash(password)
        try:
            with get_db() as conn:
                conn.execute(
                    'INSERT INTO users (nama, email, password_hash, role) VALUES (?, ?, ?, ?)',
                    (nama, email, pwd_hash, 'pasien')
                )
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email sudah terdaftar.', 'error')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute(
                'SELECT * FROM users WHERE email = ?', (email,)
            ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            if user['role'] == 'admin':
                flash('Akun ini adalah akun tenaga kesehatan, silakan login lewat halaman admin.', 'error')
                return render_template('login.html')
            
            session['user_id'] = user['id']
            session['user_nama'] = user['nama']
            session['role'] = user['role']
            flash(f'Selamat datang, {user["nama"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Email atau password salah.', 'error')
    return render_template('login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute(
                'SELECT * FROM users WHERE email = ?', (email,)
            ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            if user['role'] == 'pasien':
                flash('Akun ini bukan akun tenaga kesehatan, silakan login lewat halaman pasien.', 'error')
                return render_template('admin_login.html')
            
            session['user_id'] = user['id']
            session['user_nama'] = user['nama']
            session['role'] = user['role']
            flash(f'Selamat datang, {user["nama"]}!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Email atau password salah.', 'error')
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Kamu telah keluar.', 'info')
    return redirect(url_for('index'))

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
@role_required('pasien')
def dashboard():
    uid = session['user_id']
    with get_db() as conn:
        # Sleep score terbaru
        latest_log = conn.execute(
            '''SELECT * FROM daily_logs WHERE patient_id = ?
               ORDER BY tanggal DESC LIMIT 1''', (uid,)
        ).fetchone()
        # 7 hari terakhir untuk mini chart
        logs_7 = conn.execute(
            '''SELECT tanggal, sleep_score, kategori FROM daily_logs
               WHERE patient_id = ? ORDER BY tanggal DESC LIMIT 7''', (uid,)
        ).fetchall()
        # Analisis dari tenaga kesehatan (semua riwayat, paling baru di atas)
        all_analisis = conn.execute(
            '''SELECT a.*, u.nama as admin_nama 
               FROM analisis_awal a
               LEFT JOIN users u ON a.created_by_admin_id = u.id
               WHERE a.patient_id = ?
               ORDER BY a.tanggal DESC''', (uid,)
        ).fetchall()
        
        latest_analisis = all_analisis[0] if all_analisis else None
        analisis_history = all_analisis[1:] if len(all_analisis) > 1 else []

        # Jumlah total log
        total_logs = conn.execute(
            'SELECT COUNT(*) as cnt FROM daily_logs WHERE patient_id = ?', (uid,)
        ).fetchone()['cnt']
    return render_template('dashboard.html',
                           latest_log=latest_log,
                           logs_7=list(reversed(logs_7)),
                           latest_analisis=latest_analisis,
                           analisis_history=analisis_history,
                           total_logs=total_logs)

# ══════════════════════════════════════════════════════════════════════════════
# ANALISIS AWAL (ML)
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/analisis-awal')
@login_required
@role_required('pasien')
def analisis_awal():
    uid = session['user_id']
    with get_db() as conn:
        all_analisis = conn.execute(
            '''SELECT a.*, u.nama as admin_nama 
               FROM analisis_awal a
               LEFT JOIN users u ON a.created_by_admin_id = u.id
               WHERE a.patient_id = ?
               ORDER BY a.tanggal DESC''', (uid,)
        ).fetchall()
    return render_template('analisis_awal.html', all_analisis=all_analisis)


# ══════════════════════════════════════════════════════════════════════════════
# DAILY LOG (Rule-Based)
# ══════════════════════════════════════════════════════════════════════════════

def hitung_sleep_score(jam_mulai, jam_bangun, stres, kafein, olahraga, layar):
    """Hitung Sleep Score 0-100 berdasarkan formula rule-based."""

    # 1. Skor Jam Mulai Tidur (ideal: 21:00–23:00)
    h_mulai, m_mulai = map(int, jam_mulai.split(':'))
    menit_mulai = h_mulai * 60 + m_mulai
    ideal_start  = (21 * 60, 23 * 60)
    if ideal_start[0] <= menit_mulai <= ideal_start[1]:
        skor_mulai = 100
    else:
        if menit_mulai < ideal_start[0]:
            dev = (ideal_start[0] - menit_mulai) / 30
        else:
            dev = (menit_mulai - ideal_start[1]) / 30
        skor_mulai = max(0, 100 - dev * 10)

    # 2. Skor Jam Bangun (ideal: 05:00–07:00)
    h_bangun, m_bangun = map(int, jam_bangun.split(':'))
    menit_bangun = h_bangun * 60 + m_bangun
    ideal_wake   = (5 * 60, 7 * 60)
    if ideal_wake[0] <= menit_bangun <= ideal_wake[1]:
        skor_bangun = 100
    else:
        if menit_bangun < ideal_wake[0]:
            dev = (ideal_wake[0] - menit_bangun) / 30
        else:
            dev = (menit_bangun - ideal_wake[1]) / 30
        skor_bangun = max(0, 100 - dev * 10)

    # 3. Skor Stres (rating 1–10)
    skor_stres = (10 - int(stres)) * 10

    # 4. Skor Kafein
    skor_kafein = max(0, 100 - int(kafein) * 30)

    # 5. Skor Olahraga
    skor_olahraga = 100 if int(olahraga) >= 30 else (int(olahraga) / 30) * 100

    # 6. Skor Layar
    skor_layar = max(0, 100 - (int(layar) / 15) * 10)

    # Gabung berbobot
    sleep_score = (
        0.20 * skor_mulai +
        0.15 * skor_bangun +
        0.20 * skor_stres +
        0.15 * skor_kafein +
        0.15 * skor_olahraga +
        0.15 * skor_layar
    )

    if sleep_score >= 80:
        kategori = 'Baik'
    elif sleep_score >= 60:
        kategori = 'Cukup'
    else:
        kategori = 'Kurang'

    detail = {
        'skor_mulai': round(skor_mulai, 1),
        'skor_bangun': round(skor_bangun, 1),
        'skor_stres': round(skor_stres, 1),
        'skor_kafein': round(skor_kafein, 1),
        'skor_olahraga': round(skor_olahraga, 1),
        'skor_layar': round(skor_layar, 1),
    }

    return round(sleep_score, 1), kategori, detail


@app.route('/daily-log', methods=['GET', 'POST'])
@login_required
@role_required('pasien')
def daily_log():
    today_str = date.today().strftime('%Y-%m-%d')
    if request.method == 'GET':
        return render_template('daily_log.html', today=today_str)

    errors = {}
    form_data = request.form

    tanggal    = form_data.get('tanggal', '').strip() or today_str
    jam_mulai  = form_data.get('jam_mulai_tidur', '').strip()
    jam_bangun = form_data.get('jam_bangun', '').strip()
    stres_str  = form_data.get('tingkat_stres', '').strip()
    kafein_str = form_data.get('konsumsi_kafein', '').strip()
    olahraga_str = form_data.get('durasi_olahraga', '').strip()
    layar_str  = form_data.get('durasi_layar', '').strip()

    time_pattern = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

    if not time_pattern.match(jam_mulai):
        errors['jam_mulai_tidur'] = 'Jam mulai tidur tidak valid (format HH:MM).'
    
    if not time_pattern.match(jam_bangun):
        errors['jam_bangun'] = 'Jam bangun tidak valid (format HH:MM).'

    try:
        stres = int(stres_str)
        if not (1 <= stres <= 10):
            errors['tingkat_stres'] = 'Tingkat stres harus di antara 1 s/d 10.'
    except ValueError:
        errors['tingkat_stres'] = 'Tingkat stres harus berupa angka 1 s/d 10.'

    try:
        kafein = int(kafein_str)
        if kafein < 0:
            errors['konsumsi_kafein'] = 'Konsumsi kafein tidak boleh negatif.'
    except ValueError:
        errors['konsumsi_kafein'] = 'Konsumsi kafein harus berupa angka non-negatif.'

    try:
        olahraga = int(olahraga_str)
        if olahraga < 0:
            errors['durasi_olahraga'] = 'Durasi olahraga tidak boleh negatif.'
    except ValueError:
        errors['durasi_olahraga'] = 'Durasi olahraga harus berupa angka non-negatif.'

    try:
        layar = int(layar_str)
        if layar < 0:
            errors['durasi_layar'] = 'Screen time tidak boleh negatif.'
    except ValueError:
        errors['durasi_layar'] = 'Screen time harus berupa angka non-negatif.'

    if errors:
        flash('Silakan periksa kembali input yang belum sesuai.', 'error')
        return render_template('daily_log.html', today=tanggal, errors=errors, form_data=form_data)

    try:
        sleep_score, kategori, detail = hitung_sleep_score(
            jam_mulai, jam_bangun, stres, kafein, olahraga, layar
        )

        with get_db() as conn:
            # Cek apakah sudah ada log hari ini
            existing = conn.execute(
                'SELECT id FROM daily_logs WHERE patient_id = ? AND tanggal = ?',
                (session['user_id'], tanggal)
            ).fetchone()
            if existing:
                conn.execute(
                    '''UPDATE daily_logs SET jam_mulai_tidur=?, jam_bangun=?,
                       tingkat_stres=?, konsumsi_kafein=?, durasi_olahraga=?,
                       durasi_layar=?, sleep_score=?, kategori=?
                       WHERE patient_id=? AND tanggal=?''',
                    (jam_mulai, jam_bangun, stres, kafein, olahraga, layar,
                     sleep_score, kategori, session['user_id'], tanggal)
                )
            else:
                conn.execute(
                    '''INSERT INTO daily_logs
                       (patient_id, tanggal, jam_mulai_tidur, jam_bangun,
                        tingkat_stres, konsumsi_kafein, durasi_olahraga,
                        durasi_layar, sleep_score, kategori)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (session['user_id'], tanggal, jam_mulai, jam_bangun,
                     stres, kafein, olahraga, layar, sleep_score, kategori)
                )

        return render_template('daily_log.html',
                               today=tanggal,
                               hasil=True,
                               sleep_score=sleep_score,
                               kategori=kategori,
                               detail=detail,
                               input_data={
                                   'jam_mulai': jam_mulai,
                                   'jam_bangun': jam_bangun,
                                   'stres': stres,
                                   'kafein': kafein,
                                   'olahraga': olahraga,
                                   'layar': layar,
                                   'tanggal': tanggal
                               })
    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
        return render_template('daily_log.html', today=date.today().strftime('%Y-%m-%d'))


# ══════════════════════════════════════════════════════════════════════════════
# PROGRESS MONITORING
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/progress')
@login_required
@role_required('pasien')
def progress():
    uid = session['user_id']
    periode = request.args.get('periode', '30')  # hari
    try:
        periode = int(periode)
    except ValueError:
        periode = 30

    with get_db() as conn:
        logs = conn.execute(
            '''SELECT tanggal, sleep_score, kategori, jam_mulai_tidur,
                      jam_bangun, tingkat_stres, konsumsi_kafein,
                      durasi_olahraga, durasi_layar
               FROM daily_logs
               WHERE patient_id = ?
                 AND tanggal >= date('now', ?, 'localtime')
               ORDER BY tanggal ASC''',
            (uid, f'-{periode} days')
        ).fetchall()
        # Rata-rata
        stats = conn.execute(
            '''SELECT AVG(sleep_score) as avg_score,
                      MAX(sleep_score) as max_score,
                      MIN(sleep_score) as min_score,
                      COUNT(*) as total
               FROM daily_logs
               WHERE patient_id = ?
                 AND tanggal >= date('now', ?, 'localtime')''',
            (uid, f'-{periode} days')
        ).fetchone()

    chart_data = {
        'labels': [r['tanggal'] for r in logs],
        'scores': [r['sleep_score'] for r in logs],
        'kategori': [r['kategori'] for r in logs],
    }

    return render_template('progress_monitoring.html',
                           logs=logs,
                           chart_data=json.dumps(chart_data),
                           stats=stats,
                           periode=periode)

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    with get_db() as conn:
        pasien_list = conn.execute(
            '''SELECT u.id, u.nama, u.email, u.created_at, 
                      (SELECT a.hasil_prediksi FROM analisis_awal a WHERE a.patient_id = u.id ORDER BY a.tanggal DESC LIMIT 1) as risiko_terakhir
               FROM users u
               WHERE u.role = 'pasien'
               ORDER BY u.created_at DESC'''
        ).fetchall()
    return render_template('admin_dashboard.html', pasien_list=pasien_list)

@app.route('/admin/pasien/<int:patient_id>')
@login_required
@role_required('admin')
def admin_patient_detail(patient_id):
    with get_db() as conn:
        pasien = conn.execute('SELECT * FROM users WHERE id = ? AND role = "pasien"', (patient_id,)).fetchone()
        if not pasien:
            flash('Pasien tidak ditemukan.', 'error')
            return redirect(url_for('admin_dashboard'))
            
        all_analisis = conn.execute(
            '''SELECT a.*, u.nama as admin_nama 
               FROM analisis_awal a
               LEFT JOIN users u ON a.created_by_admin_id = u.id
               WHERE a.patient_id = ?
               ORDER BY a.tanggal DESC''', (patient_id,)
        ).fetchall()
        
        latest_analisis = all_analisis[0] if all_analisis else None
        
        logs = conn.execute(
            '''SELECT * FROM daily_logs WHERE patient_id = ?
               ORDER BY tanggal ASC''', (patient_id,)
        ).fetchall()
        
        stats = conn.execute(
            '''SELECT AVG(sleep_score) as avg_score,
                      COUNT(*) as total
               FROM daily_logs WHERE patient_id = ?''', (patient_id,)
        ).fetchone()

    chart_data = {
        'labels': [r['tanggal'] for r in logs],
        'scores': [r['sleep_score'] for r in logs],
        'kategori': [r['kategori'] for r in logs],
    }
    
    return render_template('admin_patient_detail.html',
                           pasien=pasien,
                           latest_analisis=latest_analisis,
                           all_analisis=all_analisis,
                           logs=logs,
                           stats=stats,
                           chart_data=json.dumps(chart_data))

@app.route('/admin/pasien/<int:patient_id>/analisis', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_analisis_pasien(patient_id):
    with get_db() as conn:
        pasien = conn.execute('SELECT * FROM users WHERE id = ? AND role = "pasien"', (patient_id,)).fetchone()
        if not pasien:
            flash('Pasien tidak ditemukan.', 'error')
            return redirect(url_for('admin_dashboard'))

    if request.method == 'GET':
        return render_template('admin_analisis_pasien.html', pasien=pasien, occupations=OCCUPATIONS)

    errors = {}
    form_data = request.form

    gender     = form_data.get('gender', '').strip()
    if gender not in ['Male', 'Female']:
        errors['gender'] = 'Pilih jenis kelamin yang valid (Male/Female).'

    try:
        age = float(form_data.get('age', ''))
        if not (1.0 <= age <= 120.0):
            errors['age'] = 'Usia harus di antara 1 s/d 120 tahun.'
    except ValueError:
        errors['age'] = 'Usia harus berupa angka 1 - 120.'

    occupation = form_data.get('occupation', '').strip()
    if occupation not in OCCUPATIONS:
        errors['occupation'] = 'Pilih pekerjaan yang valid.'

    bmi = form_data.get('bmi_category', '').strip()
    if bmi not in ['Normal', 'Overweight', 'Obese']:
        errors['bmi_category'] = 'Pilih kategori BMI yang valid.'

    try:
        sleep_dur = float(form_data.get('sleep_duration', ''))
        if not (0.0 <= sleep_dur <= 24.0):
            errors['sleep_duration'] = 'Durasi tidur harus di antara 0 s/d 24 jam.'
    except ValueError:
        errors['sleep_duration'] = 'Durasi tidur harus berupa angka 0 - 24.'

    try:
        quality = float(form_data.get('quality_of_sleep', ''))
        if not (1.0 <= quality <= 10.0):
            errors['quality_of_sleep'] = 'Kualitas tidur harus di antara skala 1 s/d 10.'
    except ValueError:
        errors['quality_of_sleep'] = 'Kualitas tidur harus berupa angka 1 - 10.'

    try:
        phys_act = float(form_data.get('physical_activity', ''))
        if phys_act < 0:
            errors['physical_activity'] = 'Aktivitas fisik tidak boleh negatif.'
    except ValueError:
        errors['physical_activity'] = 'Aktivitas fisik harus berupa angka.'

    try:
        stress = float(form_data.get('stress_level', ''))
        if not (1.0 <= stress <= 10.0):
            errors['stress_level'] = 'Tingkat stres harus di antara skala 1 s/d 10.'
    except ValueError:
        errors['stress_level'] = 'Tingkat stres harus berupa angka 1 - 10.'

    try:
        heart_rate = float(form_data.get('heart_rate', ''))
        if heart_rate <= 0:
            errors['heart_rate'] = 'Detak jantung harus lebih besar dari 0.'
    except ValueError:
        errors['heart_rate'] = 'Detak jantung harus berupa angka.'

    try:
        daily_steps = float(form_data.get('daily_steps', ''))
        if daily_steps < 0:
            errors['daily_steps'] = 'Langkah harian tidak boleh negatif.'
    except ValueError:
        errors['daily_steps'] = 'Langkah harian harus berupa angka.'

    try:
        systolic = float(form_data.get('blood_pressure_systolic', ''))
        if not (70.0 <= systolic <= 200.0):
            errors['blood_pressure_systolic'] = 'Tekanan darah sistolik harus di antara 70 s/d 200 mmHg.'
    except ValueError:
        errors['blood_pressure_systolic'] = 'Sistolik harus berupa angka 70 - 200.'

    try:
        diastolic = float(form_data.get('blood_pressure_diastolic', ''))
        if not (40.0 <= diastolic <= 130.0):
            errors['blood_pressure_diastolic'] = 'Tekanan darah diastolik harus di antara 40 s/d 130 mmHg.'
    except ValueError:
        errors['blood_pressure_diastolic'] = 'Diastolik harus berupa angka 40 - 130.'

    catatan_admin = form_data.get('catatan_admin', '').strip()

    if errors:
        flash('Silakan periksa kembali input form analisis.', 'error')
        return render_template('admin_analisis_pasien.html', pasien=pasien, occupations=OCCUPATIONS, errors=errors, form_data=form_data)

    try:
        gender_enc     = le_gender.transform([gender])[0]
        occupation_enc = le_occupation.transform([occupation])[0]
        bmi_enc        = le_bmi.transform([bmi])[0]

        features = np.array([[
            gender_enc, age, occupation_enc, sleep_dur, quality,
            phys_act, stress, bmi_enc, heart_rate, daily_steps,
            systolic, diastolic
        ]])

        pred_encoded = rf_model.predict(features)[0]
        pred_label   = le_target.inverse_transform([pred_encoded])[0]
        pred_proba   = rf_model.predict_proba(features)[0]
        class_labels = list(le_target.inverse_transform(rf_model.classes_))
        proba_dict   = dict(zip(class_labels, [round(float(p)*100, 1) for p in pred_proba]))

        explainer  = shap.TreeExplainer(rf_model)
        shap_vals  = explainer.shap_values(features)
        pred_class_idx = list(rf_model.classes_).index(pred_encoded)
        if isinstance(shap_vals, list):
            shap_for_pred = shap_vals[pred_class_idx][0]
        else:
            if len(shap_vals.shape) == 3:
                shap_for_pred = shap_vals[0, :, pred_class_idx]
            else:
                shap_for_pred = shap_vals[0]

        shap_dict = {
            col: round(float(val), 4)
            for col, val in zip(FEATURE_COLUMNS, shap_for_pred)
        }
        shap_sorted = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)

        shap_text = '\n'.join([f'  - {k}: {v:+.4f}' for k, v in shap_sorted[:6]])
        prompt_gemini = f"""
Kamu adalah asisten kesehatan tidur profesional. Seorang tenaga kesehatan baru saja menjalankan analisis risiko gangguan tidur untuk pasien '{pasien['nama']}'.

Hasil prediksi model Machine Learning:
- Risiko terdeteksi: {pred_label}
- Probabilitas: {json.dumps(proba_dict, ensure_ascii=False)}

Kontribusi fitur utama (nilai SHAP, positif = meningkatkan risiko ini):
{shap_text}

Berikan respons dalam bahasa Indonesia yang ramah dan mudah dipahami pasien, dengan format PERSIS seperti ini:

**PENJELASAN:**
(2-3 kalimat penjelasan mengapa hasil prediksinya seperti itu, berdasarkan kontribusi fitur)

**REKOMENDASI:**
1. (rekomendasi konkret dan actionable)
2. (rekomendasi konkret dan actionable)
3. (rekomendasi konkret dan actionable)
4. (rekomendasi konkret dan actionable)
5. (rekomendasi konkret dan actionable)

Jangan gunakan jargon medis yang rumit. Fokus pada gaya hidup yang bisa diperbaiki.
"""
        try:
            gemini_response = gemini_model.generate_content(prompt_gemini)
            penjelasan_gemini = gemini_response.text
        except Exception as e:
            penjelasan_gemini = f"[Penjelasan AI tidak tersedia: {str(e)}]"

        input_data = {
            'gender': gender, 'age': age, 'occupation': occupation,
            'sleep_duration': sleep_dur, 'quality_of_sleep': quality,
            'physical_activity': phys_act, 'stress_level': stress,
            'bmi_category': bmi, 'heart_rate': heart_rate,
            'daily_steps': daily_steps, 'systolic': systolic, 'diastolic': diastolic
        }

        with get_db() as conn:
            conn.execute(
                '''INSERT INTO analisis_awal
                   (patient_id, created_by_admin_id, tanggal, input_data_json, hasil_prediksi,
                    probabilitas_json, shap_values_json, penjelasan_gemini, catatan_admin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (patient_id, session['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                 json.dumps(input_data), pred_label,
                 json.dumps(proba_dict), json.dumps(shap_dict),
                 penjelasan_gemini, catatan_admin)
            )

        flash(f'Analisis awal untuk pasien {pasien["nama"]} berhasil disimpan!', 'success')
        return redirect(url_for('admin_patient_detail', patient_id=patient_id))

    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'error')
        return render_template('admin_analisis_pasien.html', pasien=pasien, occupations=OCCUPATIONS)

# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app.run(debug=True, port=5000)
