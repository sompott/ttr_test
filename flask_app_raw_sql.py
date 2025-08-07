
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import mysql.connector
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# MySQL connection
def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='your_mysql_user',
        password='your_mysql_password',
        database='it_equipment_db'
    )

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('SELECT COUNT(*) AS count FROM equipment')
    total_equipment = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM equipment WHERE status = 'Available'")
    available_equipment = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM equipment WHERE status = 'In_Use'")
    in_use_equipment = cursor.fetchone()['count']

    cursor.execute('SELECT COUNT(*) AS count FROM employees')
    total_employees = cursor.fetchone()['count']

    cursor.execute('SELECT COUNT(*) AS count FROM software_licenses')
    total_licenses = cursor.fetchone()['count']

    cursor.execute('''
        SELECT equipment_type,
               COUNT(*) AS total,
               SUM(status = 'Available') AS available,
               SUM(status = 'In_Use') AS in_use
        FROM equipment
        GROUP BY equipment_type
    ''')
    equipment_by_type = cursor.fetchall()

    cursor.execute('SELECT * FROM software_licenses')
    licenses = cursor.fetchall()

    license_usage = []
    for license in licenses:
        license_id = license['id']
        cursor.execute('SELECT COUNT(*) AS count FROM software_installations WHERE license_id = %s AND status = "Active"', (license_id,))
        used = cursor.fetchone()['count']
        remaining = license['max_installations'] - used
        license['used'] = used
        license['remaining'] = remaining
        license_usage.append({'license': license, 'used': used, 'remaining': remaining})

    cursor.close()
    conn.close()

    return render_template('dashboard.html', total_equipment=total_equipment,
                           available_equipment=available_equipment,
                           in_use_equipment=in_use_equipment,
                           total_employees=total_employees,
                           total_licenses=total_licenses,
                           equipment_by_type=equipment_by_type,
                           license_usage=license_usage)

@app.route('/employees')
def employees():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM employees')
    employees = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('employees.html', employees=employees)

@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        data = (
            request.form['employee_id'],
            request.form['first_name'],
            request.form['last_name'],
            request.form['department'],
            request.form['position'],
            request.form['email'],
            request.form.get('phone', ''),
            datetime.now()
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO employees (employee_id, first_name, last_name, department, position, email, phone, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', data)
            conn.commit()
            flash('เพิ่มข้อมูลพนักงานสำเร็จ!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'เกิดข้อผิดพลาด: {e}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('employees'))

    return render_template('employee_form.html')

@app.route('/equipment')
def equipment():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM equipment')
    equipment_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('equipment.html', equipment=equipment_list)

@app.route('/equipment/add', methods=['GET', 'POST'])
def add_equipment():
    if request.method == 'POST':
        data = (
            request.form['asset_tag'],
            request.form['equipment_type'],
            request.form['brand'],
            request.form['model'],
            request.form.get('serial_number', ''),
            request.form.get('specifications', ''),
            request.form.get('purchase_date') or None,
            request.form.get('warranty_expire') or None,
            'Available',
            request.form.get('location', ''),
            datetime.now()
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO equipment (asset_tag, equipment_type, brand, model, serial_number, specifications,
                purchase_date, warranty_expire, status, location, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', data)
            conn.commit()
            flash('เพิ่มอุปกรณ์สำเร็จ!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'เกิดข้อผิดพลาด: {e}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('equipment'))

    return render_template('equipment_form.html')

@app.route('/licenses')
def licenses():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM software_licenses')
    licenses = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('licenses.html', licenses=licenses)

@app.route('/licenses/add', methods=['GET', 'POST'])
def add_license():
    if request.method == 'POST':
        data = (
            request.form['license_key'],
            request.form['software_type'],
            request.form['license_type'],
            request.form['product_name'],
            request.form.get('version', ''),
            request.form.get('purchase_date') or None,
            request.form.get('expiry_date') or None,
            int(request.form.get('max_installations', 1)),
            request.form.get('vendor', ''),
            float(request.form['cost']) if request.form.get('cost') else None,
            request.form.get('notes', ''),
            datetime.now()
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO software_licenses (license_key, software_type, license_type, product_name, version,
                purchase_date, expiry_date, max_installations, vendor, cost, notes, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', data)
            conn.commit()
            flash('เพิ่ม License สำเร็จ!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'เกิดข้อผิดพลาด: {e}', 'error')
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('licenses'))

    return render_template('license_form.html')

@app.route('/api/equipment-summary')
def equipment_summary_api():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT equipment_type, status, COUNT(*) AS count
        FROM equipment
        GROUP BY equipment_type, status
    ''')
    summary = cursor.fetchall()
    cursor.close()
    conn.close()

    result = {}
    for item in summary:
        etype = item['equipment_type']
        if etype not in result:
            result[etype] = {}
        result[etype][item['status']] = item['count']
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
