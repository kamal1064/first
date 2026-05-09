"""
Employee Management System - Flask Backend
==========================================
Run with: python app.py
"""


from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import sqlite3
import hashlib
import os
import csv
import io
from datetime import datetime, date
from functools import wraps
import pyotp
import qrcode
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'emp_mgmt_secret_key_2024'  # Change in production

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────


def get_db():
    """Connect to SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-like access
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    c = conn.cursor()

    # Users table (owners/admins)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            otp_secret TEXT,
            otp_enabled BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Add OTP columns to existing users table if they don't exist
    try:
        c.execute('ALTER TABLE users ADD COLUMN otp_secret TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE users ADD COLUMN otp_enabled BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    #part time mployee table
    # Part Time Employees
    c.execute('''
        CREATE TABLE IF NOT EXISTS part_time_employee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_name TEXT NOT NULL,
        working_date TEXT NOT NULL,
        slab_quantity INTEGER NOT NULL,
        slab_price REAL NOT NULL,
        total_price REAL NOT NULL,
        delivery_location TEXT NOT NULL,
        user_id INTEGER
        )
    ''')

    # Employees table
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            age INTEGER,
            gender TEXT,
            salary REAL,
            leaves INTEGER DEFAULT 0,
            working_hours REAL DEFAULT 40,
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Attendance table
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(emp_id, date),
            FOREIGN KEY (emp_id) REFERENCES employees(id)
        )
    ''')

    # Salary records table
    c.execute('''
        CREATE TABLE IF NOT EXISTS salary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            present_days INTEGER DEFAULT 0,
            total_salary REAL DEFAULT 0,
            advance_amount_paid REAL DEFAULT 0,
            advance_paid_at TEXT,
            payment_status TEXT DEFAULT 'Unpaid',
            paid_at TEXT,
            FOREIGN KEY (emp_id) REFERENCES employees(id)
        )
    ''')

    # Ensure columns exist for existing DBs
    try:
        c.execute('ALTER TABLE salary_records ADD COLUMN advance_amount_paid REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE salary_records ADD COLUMN advance_paid_at TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Part time employees table (ensure advance columns exist for existing DBs)
    try:
        c.execute('ALTER TABLE part_time_employee ADD COLUMN advance_amount_paid REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE part_time_employee ADD COLUMN advance_paid_at TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()

# Ensure DB schema exists in all deployment modes (not just __main__)
# Important for hosts that import the app via WSGI.
try:
    init_db()
except Exception:
    # If DB isn't writable yet, the app may still start; schema will be handled on first request.
    pass

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────


def hash_password(password):
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Decorator to protect routes that need login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Check if OTP verification is pending
        if session.get('otp_pending'):
            return redirect(url_for('verify_otp'))

        return f(*args, **kwargs)
    return decorated


def get_current_user_id():
    return session.get('user_id')

# ─────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            return render_template('signup.html', error='All fields are required.')

        conn = get_db()
        try:
            conn.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hash_password(password))
            )
            conn.commit()
            return redirect(url_for('login', success='Account created! Please login.'))
        except sqlite3.IntegrityError:
            return render_template('signup.html', error='Username or email already exists.')
        finally:
            conn.close()

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    success = request.args.get('success')
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, hash_password(password))
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']

            # Check if OTP is enabled for this user
            if user['otp_enabled']:
                session['otp_pending'] = True
                return redirect(url_for('verify_otp'))
            else:
                return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials.')

    return render_template('login.html', success=success)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─────────────────────────────────────────
# OTP AUTHENTICATION
# ─────────────────────────────────────────

@app.route('/otp/setup')
@login_required
def otp_setup():
    user_id = get_current_user_id()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()

    if user['otp_enabled']:
        return redirect(url_for('dashboard'))

    # Generate new OTP secret
    otp_secret = pyotp.random_base32()
    totp = pyotp.TOTP(otp_secret)

    # Generate QR code
    uri = totp.provisioning_uri(name=user['email'], issuer_name="Employee Management System")
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64 for display
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code = base64.b64encode(buffer.getvalue()).decode()

    return render_template('otp_setup.html', qr_code=qr_code, otp_secret=otp_secret)


@app.route('/otp/setup/confirm', methods=['POST'])
@login_required
def otp_setup_confirm():
    otp_secret = request.form.get('otp_secret')
    otp_code = request.form.get('otp_code')

    if not otp_secret or not otp_code:
        return render_template('otp_setup.html', error='All fields are required.')

    totp = pyotp.TOTP(otp_secret)
    if totp.verify(otp_code):
        user_id = get_current_user_id()
        conn = get_db()
        conn.execute(
            'UPDATE users SET otp_secret = ?, otp_enabled = 1 WHERE id = ?',
            (otp_secret, user_id)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))
    else:
        # Regenerate QR code for retry
        totp = pyotp.TOTP(otp_secret)
        uri = totp.provisioning_uri(name=session['username'], issuer_name="Employee Management System")
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code = base64.b64encode(buffer.getvalue()).decode()

        return render_template('otp_setup.html', qr_code=qr_code, otp_secret=otp_secret, error='Invalid OTP code. Please try again.')


@app.route('/otp/verify', methods=['GET', 'POST'])
def verify_otp():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if not session.get('otp_pending'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code')

        if not otp_code:
            return render_template('otp_verify.html', error='OTP code is required.')

        user_id = get_current_user_id()
        conn = get_db()
        user = conn.execute('SELECT otp_secret FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

        if user and user['otp_secret']:
            totp = pyotp.TOTP(user['otp_secret'])
            if totp.verify(otp_code):
                session.pop('otp_pending', None)
                return redirect(url_for('dashboard'))
            else:
                return render_template('otp_verify.html', error='Invalid OTP code.')
        else:
            return render_template('otp_verify.html', error='OTP not configured.')

    return render_template('otp_verify.html')


@app.route('/otp/disable', methods=['POST'])
@login_required
def otp_disable():
    user_id = get_current_user_id()
    conn = get_db()
    conn.execute(
        'UPDATE users SET otp_secret = NULL, otp_enabled = 0 WHERE id = ?',
        (user_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────


@app.route('/dashboard')
@login_required
def dashboard():
    uid = get_current_user_id()
    conn = get_db()

    # Get user OTP status
    user = conn.execute('SELECT otp_enabled FROM users WHERE id = ?', (uid,)).fetchone()
    otp_enabled = user['otp_enabled'] if user else False

    # Summary stats
    employees = conn.execute(
        'SELECT * FROM employees WHERE user_id = ?', (uid,)).fetchall()
    total_emp = len(employees)
    avg_salary = round(sum(e['salary']
                       for e in employees) / total_emp, 2) if total_emp else 0
    avg_age = round(sum(e['age'] for e in employees) /
                    total_emp, 1) if total_emp else 0
    total_hrs = sum(e['working_hours'] for e in employees)

    # Attendance chart data (last 30 days across all employees)
    today = date.today().isoformat()
    att_data = conn.execute('''
        SELECT status, COUNT(*) as cnt FROM attendance
        WHERE emp_id IN (SELECT id FROM employees WHERE user_id = ?)
        GROUP BY status
    ''', (uid,)).fetchall()
    present_count = next((r['cnt']
                         for r in att_data if r['status'] == 'Present'), 0)
    absent_count = next((r['cnt']
                        for r in att_data if r['status'] == 'Absent'), 0)

    # Salary distribution for chart
    salary_data = [{'name': e['name'], 'salary': e['salary']}
                   for e in employees]

    # Recent attendance
    recent_att = conn.execute('''
        SELECT e.name, a.date, a.status FROM attendance a
        JOIN employees e ON e.id = a.emp_id
        WHERE e.user_id = ?
        ORDER BY a.date DESC LIMIT 10
    ''', (uid,)).fetchall()

    conn.close()

    return render_template('dashboard.html',
                           total_emp=total_emp,
                           avg_salary=avg_salary,
                           avg_age=avg_age,
                           total_hrs=total_hrs,
                           present_count=present_count,
                           absent_count=absent_count,
                           salary_data=salary_data,
                           recent_att=recent_att,
                           today=today,
                           otp_enabled=otp_enabled
                           )

# ─────────────────────────────────────────
# EMPLOYEES
# ─────────────────────────────────────────


@app.route('/employees')
@login_required
def employees():
    uid = get_current_user_id()
    search = request.args.get('q', '').strip()
    conn = get_db()

    if search:
        emps = conn.execute(
            "SELECT * FROM employees WHERE user_id = ? AND name LIKE ? ORDER BY name",
            (uid, f'%{search}%')
        ).fetchall()
    else:
        emps = conn.execute(
            "SELECT * FROM employees WHERE user_id = ? ORDER BY name",
            (uid,)
        ).fetchall()

    conn.close()
    return render_template('employees.html', employees=emps, search=search)


@app.route('/employees/add', methods=['POST'])
@login_required
def add_employee():
    uid = get_current_user_id()
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    age = int(request.form.get('age', 0))
    gender = request.form.get('gender', '')
    salary = float(request.form.get('salary', 0))
    leaves = int(request.form.get('leaves', 0))
    hours = float(request.form.get('working_hours', 40))

    if not name:
        return redirect(url_for('employees'))

    conn = get_db()
    conn.execute(
        'INSERT INTO employees (name, phone, age, gender, salary, leaves, working_hours, user_id) VALUES (?,?,?,?,?,?,?,?)',
        (name, phone, age, gender, salary, leaves, hours, uid)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('employees'))


@app.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
def edit_employee(emp_id):
    uid = get_current_user_id()
    conn = get_db()

    if request.method == 'POST':
        conn.execute('''
            UPDATE employees SET name=?, phone=?, age=?, gender=?, salary=?, leaves=?, working_hours=?
            WHERE id=? AND user_id=?
        ''', (
            request.form.get('name'),
            request.form.get('phone'),
            int(request.form.get('age', 0)),
            request.form.get('gender'),
            float(request.form.get('salary', 0)),
            int(request.form.get('leaves', 0)),
            float(request.form.get('working_hours', 40)),
            emp_id, uid
        ))
        conn.commit()
        conn.close()
        return redirect(url_for('employees'))

    emp = conn.execute(
        'SELECT * FROM employees WHERE id=? AND user_id=?', (emp_id, uid)).fetchone()
    conn.close()
    if not emp:
        return redirect(url_for('employees'))
    return render_template('edit_employee.html', emp=emp)


@app.route('/employees/delete/<int:emp_id>', methods=['POST'])
@login_required
def delete_employee(emp_id):
    uid = get_current_user_id()
    conn = get_db()
    # Delete related records first
    conn.execute('DELETE FROM attendance WHERE emp_id=?', (emp_id,))
    conn.execute('DELETE FROM salary_records WHERE emp_id=?', (emp_id,))
    conn.execute(
        'DELETE FROM employees WHERE id=? AND user_id=?', (emp_id, uid))
    conn.commit()
    conn.close()
    return redirect(url_for('employees'))

# ─────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────


@app.route('/attendance')
@login_required
def attendance():
    uid = get_current_user_id()
    selected_date = request.args.get('date', date.today().isoformat())
    conn = get_db()

    emps = conn.execute(
        'SELECT * FROM employees WHERE user_id=? ORDER BY name',
        (uid,)
    ).fetchall()

    # Default everyone to Present
    att_map = {}

    for e in emps:
        att_map[e['id']] = 'Present'

    # Load only absent records from DB
    records = conn.execute(
        'SELECT emp_id, status FROM attendance WHERE date=?',
        (selected_date,)
    ).fetchall()

    for r in records:
        att_map[r['emp_id']] = r['status']

    conn.close()

    return render_template(
        'attendance.html',
        employees=emps,
        att_map=att_map,
        selected_date=selected_date,
        today=date.today().isoformat()
    )
@app.route('/attendance/mark', methods=['POST'])
@login_required

def mark_attendance():
    data = request.get_json()

    emp_id = data.get('emp_id')
    att_date = data.get('date')
    status = data.get('status')

    if not all([emp_id, att_date, status]):
        return jsonify({'success': False})

    conn = get_db()

    try:
        # If marked Present → remove record
        # because Present is now the default state
        if status == 'Present':
            conn.execute(
                'DELETE FROM attendance WHERE emp_id=? AND date=?',
                (emp_id, att_date)
            )

        else:
            # Store ONLY absent entries
            conn.execute('''
                INSERT INTO attendance (emp_id, date, status)
                VALUES (?, ?, ?)
                ON CONFLICT(emp_id, date)
                DO UPDATE SET status=excluded.status
            ''', (emp_id, att_date, status))

        conn.commit()

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

    finally:
        conn.close()


@app.route('/attendance/summary')
@login_required
def attendance_summary():
    uid = get_current_user_id()
    month_filter = request.args.get('month', datetime.now().strftime('%Y-%m'))
    conn = get_db()

    emps = conn.execute(
        'SELECT * FROM employees WHERE user_id=? ORDER BY name', (uid,)).fetchall()

    summary = []
    today = date.today()
    
    # Calculate total days for the month
    if month_filter == today.strftime('%Y-%m'):
        total_days = today.day
    else:
        total_days = 30
    
    for e in emps:
        absent_days = conn.execute('''
            SELECT COUNT(*) as cnt
            FROM attendance
            WHERE emp_id=?
            AND status='Absent'
            AND substr(date,1,7)=?
        ''', (e['id'], month_filter)).fetchone()['cnt']

        # Present days
        present_days = total_days - absent_days

        summary.append({
            'name': e['name'],
            'present': present_days,
            'absent': absent_days,
            'total': total_days
        })

    conn.close()
    return render_template('attendance_summary.html',
                           summary=summary,
                           month_filter=month_filter
                           )

# ─────────────────────────────────────────
# SALARY
# ─────────────────────────────────────────


@app.route('/salary')
@login_required
def salary():

    uid = get_current_user_id()

    month_filter = request.args.get(
        'month',
        datetime.now().strftime('%Y-%m')
    )

    conn = get_db()

    emps = conn.execute(
        'SELECT * FROM employees WHERE user_id=? ORDER BY name',
        (uid,)
    ).fetchall()

    salary_details = []

    for e in emps:

        # Total working days
        today = date.today()

        if month_filter == today.strftime('%Y-%m'):
            total_days = today.day
        else:
            total_days = 30

        # Count absent days only
        absent_days = conn.execute('''
            SELECT COUNT(*) as cnt
            FROM attendance
            WHERE emp_id=?
            AND date LIKE ?
            AND status='Absent'
        ''', (
            e['id'],
            f'{month_filter}%'
        )).fetchone()['cnt']

        # Present days
        present_days = total_days - absent_days

        # Salary calculation
        salary_per_day = e['salary'] / 30

        final_salary = round(
            salary_per_day * present_days,
            2
        )

        # Check existing salary record
        rec = conn.execute('''
            SELECT *
            FROM salary_records
            WHERE emp_id=? AND month=?
        ''', (
            e['id'],
            month_filter
        )).fetchone()

        # Insert new record
        if not rec:

            conn.execute('''
                INSERT INTO salary_records (
                    emp_id,
                    month,
                    present_days,
                    total_salary,
                    payment_status
                )

                VALUES (?, ?, ?, ?, 'Unpaid')
            ''', (
                e['id'],
                month_filter,
                present_days,
                final_salary
            ))

            conn.commit()

            payment_status = 'Unpaid'
            paid_at = None

        else:

            conn.execute('''
                UPDATE salary_records
                SET present_days=?,
                    total_salary=?
                WHERE emp_id=?
                AND month=?
                AND payment_status='Unpaid'
            ''', (
                present_days,
                final_salary,
                e['id'],
                month_filter
            ))

            conn.commit()

            payment_status = rec['payment_status']
            paid_at = rec['paid_at']

        advance_amount_paid = rec['advance_amount_paid'] if rec else 0
        advance_paid_at = rec['advance_paid_at'] if rec else None

        net_delta = round(final_salary - advance_amount_paid, 2)

        salary_details.append({
            'id': e['id'],
            'name': e['name'],
            'monthly_salary': e['salary'],
            'present_days': present_days,
            'salary_per_day': round(salary_per_day, 2),
            'final_salary': final_salary,
            'advance_amount_paid': advance_amount_paid,
            'advance_paid_at': advance_paid_at,
            'net_delta': net_delta,
            'payment_status': payment_status,
            'paid_at': paid_at
        })

    conn.close()

    return render_template(
        'salary.html',
        salary_details=salary_details,
        month_filter=month_filter
    )

@app.route('/part-time')
@login_required
def part_time():

    uid = get_current_user_id()

    conn = get_db()

    records = conn.execute('''
        SELECT *
        FROM part_time_employee
        WHERE user_id=?
        ORDER BY id DESC
    ''', (uid,)).fetchall()

    conn.close()

    return render_template(
        'Part_time_employee.html',
        records=records
    )


@app.route('/part-time/add', methods=['POST'])
@login_required
def add_part_time_work():

    uid = get_current_user_id()

    employee_name = request.form.get('employee_name')
    working_date = request.form.get('working_date')
    location = request.form.get('location')

    slab_quantity = int(
        request.form.get('slab_quantity')
    )

    slab_price = float(
        request.form.get('slab_price')
    )

    total_price = slab_quantity * slab_price

    conn = get_db()

    conn.execute('''
        INSERT INTO part_time_employee
        (
            employee_name,
            working_date,
            delivery_location,
            slab_quantity,
            slab_price,
            total_price,
            user_id
        )

        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        employee_name,
        working_date,
        location,
        slab_quantity,
        slab_price,
        total_price,
        uid
    ))

    conn.commit()
    conn.close()

    return redirect(url_for('part_time'))



@app.route('/salary/mark_paid', methods=['POST'])
@login_required
def mark_paid():
    data = request.get_json()
    emp_id = data.get('emp_id')
    month = data.get('month')
    paid_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    conn.execute('''
        UPDATE salary_records SET payment_status='Paid', paid_at=?
        WHERE emp_id=? AND month=?
    ''', (paid_at, emp_id, month))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'paid_at': paid_at})

@app.route('/salary/set_advance', methods=['POST'])
@login_required
def salary_set_advance():
    data = request.get_json()
    emp_id = data.get('emp_id')
    month = data.get('month')
    advance_amount_paid = data.get('advance_amount_paid')

    try:
        advance_amount_paid = float(advance_amount_paid)
        if advance_amount_paid < 0:
            return jsonify({'success': False, 'message': 'Advance must be >= 0'}), 400
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Advance must be a number'}), 400

    advance_paid_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()

    # Update advance in DB
    conn.execute('''
        UPDATE salary_records
        SET advance_amount_paid=?,
            advance_paid_at=?
        WHERE emp_id=? AND month=? AND payment_status IN ('Unpaid','Paid')
    ''', (advance_amount_paid, advance_paid_at, emp_id, month))
    conn.commit()

    # Recompute net delta using stored final_salary (total_salary)
    rec = conn.execute('''
        SELECT total_salary, advance_amount_paid
        FROM salary_records
        WHERE emp_id=? AND month=?
    ''', (emp_id, month)).fetchone()

    conn.close()

    if not rec:
        return jsonify({'success': False, 'message': 'Salary record not found'}), 404

    total_salary = float(rec['total_salary'] or 0)
    current_advance = float(rec['advance_amount_paid'] or 0)
    net_delta = round(total_salary - current_advance, 2)

    return jsonify({
        'success': True,
        'advance_amount_paid': advance_amount_paid,
        'advance_paid_at': advance_paid_at,
        'net_delta': net_delta,
        'payable_type': 'take_back' if net_delta < 0 else 'payable'
    })


@app.route('/part-time/set_advance', methods=['POST'])
@login_required
def part_time_set_advance():
    data = request.get_json()
    record_id = data.get('record_id')
    advance_amount_paid = data.get('advance_amount_paid')

    try:
        advance_amount_paid = float(advance_amount_paid)
        if advance_amount_paid < 0:
            return jsonify({'success': False, 'message': 'Advance must be >= 0'}), 400
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Advance must be a number'}), 400

    advance_paid_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    uid = get_current_user_id()
    conn = get_db()

    # Update only rows that belong to this user
    conn.execute('''
        UPDATE part_time_employee
        SET advance_amount_paid=?,
            advance_paid_at=?
        WHERE id=? AND user_id=?
    ''', (advance_amount_paid, advance_paid_at, record_id, uid))
    conn.commit()

    # Recompute net delta
    rec = conn.execute('''
        SELECT total_price, advance_amount_paid
        FROM part_time_employee
        WHERE id=? AND user_id=?
    ''', (record_id, uid)).fetchone()

    conn.close()

    if not rec:
        return jsonify({'success': False, 'message': 'Record not found'}), 404

    total_price = float(rec['total_price'] or 0)
    current_advance = float(rec['advance_amount_paid'] or 0)
    net_delta = round(total_price - current_advance, 2)

    return jsonify({
        'success': True,
        'advance_amount_paid': advance_amount_paid,
        'advance_paid_at': advance_paid_at,
        'net_delta': net_delta,
        'payable_type': 'take_back' if net_delta < 0 else 'payable'
    })


# ─────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────


@app.route('/export')
@login_required
def export_data():
    uid = get_current_user_id()
    conn = get_db()

    output = io.StringIO()
    writer = csv.writer(output)

    # === EMPLOYEES ===
    writer.writerow(['=== EMPLOYEES ==='])
    writer.writerow(['ID', 'Name', 'Phone', 'Age', 'Gender',
                    'Monthly Salary', 'Leaves', 'Working Hours/Week'])
    emps = conn.execute(
        'SELECT * FROM employees WHERE user_id=?', (uid,)).fetchall()
    for e in emps:
        writer.writerow([e['id'], e['name'], e['phone'], e['age'],
                        e['gender'], e['salary'], e['leaves'], e['working_hours']])

    writer.writerow([])

    # === ATTENDANCE ===
    writer.writerow(['=== ATTENDANCE ==='])
    writer.writerow(['Employee ID', 'Employee Name', 'Date', 'Status'])
    att = conn.execute('''
        SELECT a.emp_id, e.name, a.date, a.status FROM attendance a
        JOIN employees e ON e.id = a.emp_id
        WHERE e.user_id=?
        ORDER BY a.date DESC
    ''', (uid,)).fetchall()
    for a in att:
        writer.writerow([a['emp_id'], a['name'], a['date'], a['status']])

    writer.writerow([])

    # === SALARY ===
    writer.writerow(['=== SALARY RECORDS ==='])
    writer.writerow(['Employee ID', 'Employee Name', 'Month',
                    'Present Days', 'Total Salary', 'Advance Amount Paid', 'Payment Status', 'Paid At'])
    sal = conn.execute('''
        SELECT s.emp_id, e.name, s.month, s.present_days, s.total_salary, s.advance_amount_paid, s.payment_status, s.paid_at
        FROM salary_records s
        JOIN employees e ON e.id = s.emp_id
        WHERE e.user_id=?
        ORDER BY s.month DESC
    ''', (uid,)).fetchall()
    for s in sal:
        writer.writerow([s['emp_id'], s['name'], s['month'], s['present_days'],
                        s['total_salary'], s['advance_amount_paid'], s['payment_status'], s['paid_at']])

    conn.close()

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'employee_data_{date.today().isoformat()}.csv'
    )

# ─────────────────────────────────────────
# API - CHART DATA
# ─────────────────────────────────────────


@app.route('/api/chart/attendance')
@login_required
def chart_attendance():
    uid = get_current_user_id()
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    conn = get_db()

    emps = conn.execute(
        'SELECT id, name FROM employees WHERE user_id=?', (uid,)).fetchall()
    labels, present_data, absent_data = [], [], []

    for e in emps:
        p = conn.execute(
            "SELECT COUNT(*) as c FROM attendance WHERE emp_id=? AND date LIKE ? AND status='Present'",
            (e['id'], f'{month}%')
        ).fetchone()['c']
        a = conn.execute(
            "SELECT COUNT(*) as c FROM attendance WHERE emp_id=? AND date LIKE ? AND status='Absent'",
            (e['id'], f'{month}%')
        ).fetchone()['c']
        labels.append(e['name'])
        present_data.append(p)
        absent_data.append(a)

    conn.close()
    return jsonify({'labels': labels, 'present': present_data, 'absent': absent_data})

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────


if __name__ == '__main__':
    init_db()
    print("Database initialized")
    print("Starting Employee Management System...")
    print("Open: http://127.0.0.1:5000")
    app.run(debug=True)
