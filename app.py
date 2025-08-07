from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import mysql.connector
from datetime import datetime, date
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # เปลี่ยนเป็น secret key ของคุณ

# การตั้งค่าการเชื่อมต่อฐานข้อมูล
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # ใส่รหัสผ่าน MySQL ของคุณ
    'database': 'it_equipment_db',
    'charset': 'utf8'
}

def get_db_connection():
    """สร้างการเชื่อมต่อฐานข้อมูล"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

def execute_query(query, params=None, fetch=False):
    """รันคำสั่ง SQL"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or ())
        
        if fetch:
            result = cursor.fetchall()
        else:
            connection.commit()
            result = cursor.rowcount
            
        cursor.close()
        connection.close()
        return result
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# @app.route('/')
# def index():
#     """หน้าแรก - สรุปข้อมูลทั้งหมด"""
#     # สรุปจำนวนอุปกรณ์แต่ละประเภท
#     equipment_summary = execute_query("""
#         SELECT 
#             et.type_name,
#             COUNT(e.equipment_id) as total,
#             SUM(CASE WHEN e.status = 'available' THEN 1 ELSE 0 END) as available,
#             SUM(CASE WHEN e.status = 'assigned' THEN 1 ELSE 0 END) as assigned,
#             SUM(CASE WHEN e.status = 'maintenance' THEN 1 ELSE 0 END) as maintenance
#         FROM equipment_types et
#         LEFT JOIN equipments e ON et.type_id = e.type_id
#         GROUP BY et.type_id, et.type_name
#     """, fetch=True)
    
#     # สรุปจำนวนพนักงาน
#     employee_count = execute_query("""
#         SELECT 
#             COUNT(*) as total,
#             SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
#         FROM employees
#     """, fetch=True)
    
#     # สรุป License
#     license_summary = execute_query("""
#         SELECT 
#             lt.type_name,
#             lf.format_name,
#             COUNT(sl.license_id) as total,
#             SUM(sl.current_installations) as used,
#             SUM(sl.max_installations) as available_slots
#         FROM license_types lt
#         CROSS JOIN license_formats lf
#         LEFT JOIN software_licenses sl ON lt.license_type_id = sl.license_type_id AND lf.format_id = sl.format_id
#         GROUP BY lt.type_name, lf.format_name
#     """, fetch=True)
    
#     return render_template('index.html', 
#                          equipment_summary=equipment_summary,
#                          employee_count=employee_count[0] if employee_count else {'total': 0, 'active': 0},
#                          license_summary=license_summary)

@app.route('/')
def index():
    """หน้าแรก - สรุปข้อมูลทั้งหมด"""
    
    # สรุปจำนวนอุปกรณ์แต่ละประเภท (เพิ่มการกรองสถานะ)
    equipment_summary = execute_query("""
        SELECT 
            et.type_name,
            COUNT(e.equipment_id) as total,
            SUM(CASE WHEN e.status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN e.status = 'assigned' THEN 1 ELSE 0 END) as assigned,
            SUM(CASE WHEN e.status = 'maintenance' THEN 1 ELSE 0 END) as maintenance
        FROM equipment_types et
        LEFT JOIN equipments e ON et.type_id = e.type_id 
            AND (e.status IS NULL OR e.status != 'deleted')  -- ไม่รวมอุปกรณ์ที่ถูกลบ
        GROUP BY et.type_id, et.type_name
        ORDER BY et.type_name
    """, fetch=True)
    
    # สรุปจำนวนพนักงาน (ปรับให้รองรับ template)
    employee_count = execute_query("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'inactive' THEN 1 ELSE 0 END) as inactive
        FROM employees 
        WHERE status != 'deleted'  -- ไม่รวมพนักงานที่ถูกลบ
    """, fetch=True)
    
    # สรุป License (ปรับ field names ให้ตรงกับ template)
    license_summary = execute_query("""
        SELECT 
            lt.type_name,
            lf.format_name,
            COUNT(CASE WHEN sl.status = 'active' THEN sl.license_id END) as total,
            SUM(CASE WHEN sl.status = 'active' THEN sl.current_installations ELSE 0 END) as used,
            SUM(CASE WHEN sl.status = 'active' THEN sl.max_installations ELSE 0 END) as available_slots,
            COUNT(CASE WHEN sl.status = 'suspended' THEN sl.license_id END) as suspended_count,
            COUNT(CASE WHEN sl.status = 'expired' THEN sl.license_id END) as expired_count
        FROM license_types lt
        CROSS JOIN license_formats lf
        LEFT JOIN software_licenses sl ON lt.license_type_id = sl.license_type_id 
            AND lf.format_id = sl.format_id
            AND (sl.status IS NULL OR sl.status != 'deleted')  -- ไม่รวม License ที่ถูกลบ
        GROUP BY lt.type_name, lf.format_name
        ORDER BY lt.type_name, lf.format_name
    """, fetch=True)
    
    # สรุป License ที่กำลังจะหมดอายุ (30 วันข้างหน้า)
    expiring_licenses = execute_query("""
        SELECT 
            sl.license_name,
            sl.expiry_date,
            DATEDIFF(sl.expiry_date, CURDATE()) as days_left
        FROM software_licenses sl
        WHERE sl.status = 'active' 
            AND sl.expiry_date IS NOT NULL
            AND sl.expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
        ORDER BY sl.expiry_date ASC
        LIMIT 10
    """, fetch=True)
    
    # สรุปการใช้งาน License แบบรายละเอียด
    license_utilization = execute_query("""
        SELECT 
            sl.license_name,
            sl.current_installations,
            sl.max_installations,
            ROUND((sl.current_installations / sl.max_installations) * 100, 2) as utilization_percent,
            sl.status
        FROM software_licenses sl
        WHERE sl.status IN ('active', 'suspended')
            AND sl.max_installations > 0
        ORDER BY utilization_percent DESC, sl.license_name
    """, fetch=True)
    
    # จัดการข้อมูล employee_count ให้ถูกต้อง
    if employee_count and len(employee_count) > 0:
        employee_data = employee_count[0]
    else:
        employee_data = {'total': 0, 'active': 0, 'inactive': 0}
    
    return render_template('index.html', 
                         equipment_summary=equipment_summary,
                         employee_count=employee_data,
                         license_summary=license_summary)


@app.route('/employees')
def employees():
    """หน้าจัดการพนักงาน"""
    employees_list = execute_query("""
        SELECT 
            emp_id, emp_code, first_name, last_name, 
            department, position, email, phone, status
        FROM employees
        ORDER BY emp_code
    """, fetch=True)
    
    return render_template('employees.html', employees=employees_list)

@app.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    """เพิ่มพนักงานใหม่"""
    if request.method == 'POST':
        data = request.form
        
        query = """
            INSERT INTO employees (emp_code, first_name, last_name, department, position, email, phone)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (data['emp_code'], data['first_name'], data['last_name'], 
                 data['department'], data['position'], data['email'], data['phone'])
        
        result = execute_query(query, params)
        if result:
            flash('เพิ่มข้อมูลพนักงานสำเร็จ', 'success')
        else:
            flash('เกิดข้อผิดพลาดในการเพิ่มข้อมูล', 'error')
            
        return redirect(url_for('employees'))
    
    return render_template('add_employee.html')

@app.route('/equipments')
def equipments():
    """หน้าจัดการอุปกรณ์"""
    equipments_list = execute_query("""
        SELECT 
            e.equipment_id, e.equipment_code, et.type_name, e.brand, e.model,
            e.serial_number, e.status, e.location,
            CONCAT(emp.first_name, ' ', emp.last_name) as assigned_to
        FROM equipments e
        JOIN equipment_types et ON e.type_id = et.type_id
        LEFT JOIN equipment_assignments ea ON e.equipment_id = ea.equipment_id AND ea.status = 'active'
        LEFT JOIN employees emp ON ea.emp_id = emp.emp_id
        ORDER BY e.equipment_code
    """, fetch=True)
    
    return render_template('equipments.html', equipments=equipments_list)

@app.route('/equipments/delete/<int:equipment_id>', methods=['POST'])
def delete_equipment(equipment_id):
    """ลบอุปกรณ์"""
    connection = get_db_connection()
    if not connection:
        flash('เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล', 'error')
        return redirect(url_for('equipments'))

    try:
        cursor = connection.cursor()

        # ตรวจสอบว่าอุปกรณ์ยังถูกใช้งานอยู่หรือไม่
        check_assignment_query = """
            SELECT COUNT(*) FROM equipment_assignments 
            WHERE equipment_id = %s AND status = 'active'
        """
        cursor.execute(check_assignment_query, (equipment_id,))
        active_assignments = cursor.fetchone()[0]

        if active_assignments > 0:
            flash('ไม่สามารถลบอุปกรณ์ที่กำลังถูกใช้งานอยู่ได้', 'error')
            return redirect(url_for('equipments'))

        # ตรวจสอบว่าอุปกรณ์มี license ที่ติดตั้งอยู่หรือไม่
        check_license_query = """
            SELECT COUNT(*) FROM license_installations 
            WHERE equipment_id = %s AND status = 'active'
        """
        cursor.execute(check_license_query, (equipment_id,))
        active_licenses = cursor.fetchone()[0]

        if active_licenses > 0:
            flash('ไม่สามารถลบอุปกรณ์ที่มี License ติดตั้งอยู่ได้', 'error')
            return redirect(url_for('equipments'))

        # ลบอุปกรณ์
        delete_query = "DELETE FROM equipments WHERE equipment_id = %s"
        cursor.execute(delete_query, (equipment_id,))

        connection.commit()
        cursor.close()
        connection.close()

        flash('ลบอุปกรณ์สำเร็จ', 'success')

    except mysql.connector.Error as err:
        connection.rollback()
        cursor.close()
        connection.close()
        flash(f'เกิดข้อผิดพลาด: {err}', 'error')

    return redirect(url_for('equipments'))

@app.route('/equipments/add', methods=['GET', 'POST'])
def add_equipment():
    """เพิ่มอุปกรณ์ใหม่"""
    if request.method == 'POST':
        data = request.form
        
        query = """
            INSERT INTO equipments 
            (equipment_code, type_id, brand, model, serial_number, specifications, 
             purchase_date, warranty_end_date, price, location, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        purchase_date = data['purchase_date'] if data['purchase_date'] else None
        warranty_date = data['warranty_end_date'] if data['warranty_end_date'] else None
        price = float(data['price']) if data['price'] else 0
        
        params = (data['equipment_code'], data['type_id'], data['brand'], data['model'],
                 data['serial_number'], data['specifications'], purchase_date, warranty_date,
                 price, data['location'], data['notes'])
        
        result = execute_query(query, params)
        if result:
            flash('เพิ่มอุปกรณ์สำเร็จ', 'success')
        else:
            flash('เกิดข้อผิดพลาดในการเพิ่มอุปกรณ์', 'error')
            
        return redirect(url_for('equipments'))
    
    # ดึงประเภทอุปกรณ์สำหรับ dropdown
    equipment_types = execute_query("SELECT * FROM equipment_types ORDER BY type_name", fetch=True)
    return render_template('add_equipment.html', equipment_types=equipment_types)

@app.route('/assignments')
def assignments():
    """หน้าจัดการการผูกอุปกรณ์"""
    assignments_list = execute_query("""
        SELECT 
            ea.assignment_id, 
            CONCAT(emp.first_name, ' ', emp.last_name) as employee_name,
            emp.emp_code,
            e.equipment_code, et.type_name, e.brand, e.model,
            ea.assigned_date, ea.return_date, ea.status as assignment_status
        FROM equipment_assignments ea
        JOIN employees emp ON ea.emp_id = emp.emp_id
        JOIN equipments e ON ea.equipment_id = e.equipment_id
        JOIN equipment_types et ON e.type_id = et.type_id
        ORDER BY ea.assigned_date DESC
    """, fetch=True)
    
    return render_template('assignments.html', assignments=assignments_list)

@app.route('/assignments/cancel/<int:assignment_id>', methods=['POST'])
def cancel_assignment(assignment_id):
    """ยกเลิกการผูกอุปกรณ์"""
    connection = get_db_connection()
    if not connection:
        flash('เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล', 'error')
        return redirect(url_for('assignments'))

    try:
        cursor = connection.cursor()

        # ตรวจสอบว่าการผูกนี้ยังใช้งานอยู่หรือไม่
        check_query = """
            SELECT assignment_id, equipment_id, status 
            FROM equipment_assignments 
            WHERE assignment_id = %s AND status = 'active'
        """
        cursor.execute(check_query, (assignment_id,))
        assignment_info = cursor.fetchone()

        if not assignment_info:
            flash('ไม่พบการผูกอุปกรณ์ที่กำลังใช้งานอยู่', 'error')
            return redirect(url_for('assignments'))

        # อัพเดทสถานะการผูกเป็น returned และใส่วันที่คืน
        update_assignment_query = """
            UPDATE equipment_assignments 
            SET status = 'returned', return_date = CURDATE() 
            WHERE assignment_id = %s
        """
        cursor.execute(update_assignment_query, (assignment_id,))

        # อัพเดทสถานะอุปกรณ์เป็น available
        update_equipment_query = """
            UPDATE equipments 
            SET status = 'available' 
            WHERE equipment_id = %s
        """
        cursor.execute(update_equipment_query, (assignment_info[1],))

        connection.commit()
        cursor.close()
        connection.close()

        flash('ยกเลิกการผูกอุปกรณ์สำเร็จ', 'success')

    except mysql.connector.Error as err:
        connection.rollback()
        cursor.close()
        connection.close()
        flash(f'เกิดข้อผิดพลาด: {err}', 'error')

    return redirect(url_for('assignments'))

@app.route('/assignments/add', methods=['GET', 'POST'])
def add_assignment():
    """เพิ่มการผูกอุปกรณ์"""
    if request.method == 'POST':
        data = request.form
        
        # เริ่มต้น transaction
        connection = get_db_connection()
        if not connection:
            flash('เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล', 'error')
            return redirect(url_for('assignments'))
            
        try:
            cursor = connection.cursor()
            
            # เพิ่มการผูกอุปกรณ์
            assign_query = """
                INSERT INTO equipment_assignments (emp_id, equipment_id, assigned_date, notes)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(assign_query, (data['emp_id'], data['equipment_id'], 
                                        data['assigned_date'], data['notes']))
            
            # อัพเดทสถานะอุปกรณ์เป็น assigned
            update_query = "UPDATE equipments SET status = 'assigned' WHERE equipment_id = %s"
            cursor.execute(update_query, (data['equipment_id'],))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            flash('ผูกอุปกรณ์สำเร็จ', 'success')
            
        except mysql.connector.Error as err:
            connection.rollback()
            cursor.close()
            connection.close()
            flash(f'เกิดข้อผิดพลาด: {err}', 'error')
            
        return redirect(url_for('assignments'))
    
    # ดึงข้อมูลพนักงานและอุปกรณ์ที่ว่าง
    employees_list = execute_query("""
        SELECT emp_id, emp_code, CONCAT(first_name, ' ', last_name) as full_name 
        FROM employees WHERE status = 'active' ORDER BY emp_code
    """, fetch=True)
    
    available_equipments = execute_query("""
        SELECT 
            e.equipment_id, e.equipment_code, et.type_name, e.brand, e.model
        FROM equipments e
        JOIN equipment_types et ON e.type_id = et.type_id
        WHERE e.status = 'available'
        ORDER BY et.type_name, e.equipment_code
    """, fetch=True)
    
    return render_template('add_assignment.html', 
                         employees=employees_list, 
                         equipments=available_equipments)

from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime

@app.route('/licenses')
def licenses():
    """หน้าจัดการ License"""
    licenses_list = execute_query("""
        SELECT 
            sl.license_id, sl.license_key, sl.software_name, sl.version,
            lt.type_name, lf.format_name, sl.max_installations, sl.current_installations,
            sl.status, sl.expiry_date
        FROM software_licenses sl
        JOIN license_types lt ON sl.license_type_id = lt.license_type_id
        JOIN license_formats lf ON sl.format_id = lf.format_id
        ORDER BY sl.software_name, sl.version
    """, fetch=True)
    
    return render_template('licenses.html', licenses=licenses_list)

@app.route('/cancel_license', methods=['POST'])
def cancel_license():
    """ยกเลิก License"""
    try:
        data = request.get_json()
        license_id = data.get('license_id')
        
        if not license_id:
            return jsonify({'success': False, 'message': 'ไม่พบ License ID'})
        
        # ตรวจสอบว่า License มีอยู่จริงหรือไม่
        license_info = execute_query("""
            SELECT license_id, software_name, status 
            FROM software_licenses 
            WHERE license_id = %s
        """, (license_id,), fetch=True)
        
        if not license_info:
            return jsonify({'success': False, 'message': 'ไม่พบ License ที่ระบุ'})
        
        current_status = license_info[0]['status']
        
        # ตรวจสอบว่า License ยังใช้งานได้อยู่หรือไม่
        if current_status in ['cancelled', 'expired']:
            return jsonify({'success': False, 'message': 'License นี้ถูกยกเลิกหรือหมดอายุแล้ว'})
        
        # อัปเดตสถานะเป็น cancelled และเคลียร์การใช้งานปัจจุบัน
        execute_query("""
            UPDATE software_licenses 
            SET status = 'cancelled',
                current_installations = 0,
                updated_at = NOW()
            WHERE license_id = %s
        """, (license_id,))
        
        # ลบการติดตั้งทั้งหมดที่เกี่ยวข้อง (ถ้ามีตาราง installations)
        execute_query("""
            DELETE FROM license_installations 
            WHERE license_id = %s
        """, (license_id,))
        
        return jsonify({
            'success': True, 
            'message': f'ยกเลิก License {license_info[0]["software_name"]} เรียบร้อยแล้ว'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'เกิดข้อผิดพลาด: {str(e)}'})

@app.route('/reactivate_license', methods=['POST'])
def reactivate_license():
    """เปิดใช้งาน License ที่ถูกยกเลิก (กรณีต้องการกู้คืน)"""
    try:
        data = request.get_json()
        license_id = data.get('license_id')
        
        if not license_id:
            return jsonify({'success': False, 'message': 'ไม่พบ License ID'})
        
        # ตรวจสอบว่า License ถูกยกเลิกหรือไม่
        license_info = execute_query("""
            SELECT license_id, software_name, status, expiry_date 
            FROM software_licenses 
            WHERE license_id = %s
        """, (license_id,), fetch=True)
        
        if not license_info:
            return jsonify({'success': False, 'message': 'ไม่พบ License ที่ระบุ'})
        
        current_status = license_info[0]['status']
        expiry_date = license_info[0]['expiry_date']
        
        if current_status != 'cancelled':
            return jsonify({'success': False, 'message': 'License นี้ไม่ได้ถูกยกเลิก'})
        
        # ตรวจสอบวันหมดอายุ
        new_status = 'active'
        if expiry_date and datetime.now().date() > expiry_date:
            new_status = 'expired'
        
        # เปิดใช้งาน License
        execute_query("""
            UPDATE software_licenses 
            SET status = %s,
                updated_at = NOW()
            WHERE license_id = %s
        """, (new_status, license_id))
        
        return jsonify({
            'success': True, 
            'message': f'เปิดใช้งาน License {license_info[0]["software_name"]} เรียบร้อยแล้ว'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'เกิดข้อผิดพลาด: {str(e)}'})

# เพิ่ม function ช่วยเหลือสำหรับตรวจสอบ License ที่หมดอายุ
def check_expired_licenses():
    """ตรวจสอบและอัปเดต License ที่หมดอายุ"""
    execute_query("""
        UPDATE software_licenses 
        SET status = 'expired'
        WHERE expiry_date IS NOT NULL 
        AND expiry_date < CURDATE() 
        AND status = 'active'
    """)

@app.route('/licenses/add', methods=['GET', 'POST'])
def add_license():
    """เพิ่ม License ใหม่"""
    if request.method == 'POST':
        data = request.form
        
        query = """
            INSERT INTO software_licenses 
            (license_key, license_type_id, format_id, software_name, version,
             purchase_date, expiry_date, max_installations, vendor, price, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        purchase_date = data['purchase_date'] if data['purchase_date'] else None
        expiry_date = data['expiry_date'] if data['expiry_date'] else None
        price = float(data['price']) if data['price'] else 0
        max_installations = int(data['max_installations']) if data['max_installations'] else 1
        
        params = (data['license_key'], data['license_type_id'], data['format_id'],
                 data['software_name'], data['version'], purchase_date, expiry_date,
                 max_installations, data['vendor'], price, data['notes'])
        
        result = execute_query(query, params)
        if result:
            flash('เพิ่ม License สำเร็จ', 'success')
        else:
            flash('เกิดข้อผิดพลาดในการเพิ่ม License', 'error')
            
        return redirect(url_for('licenses'))
    
    # ดึงข้อมูลสำหรับ dropdown
    license_types = execute_query("SELECT * FROM license_types ORDER BY type_name", fetch=True)
    license_formats = execute_query("SELECT * FROM license_formats ORDER BY format_name", fetch=True)
    
    return render_template('add_license.html', 
                         license_types=license_types,
                         license_formats=license_formats)

@app.route('/license_installations')
def license_installations():
    """หน้าจัดการการติดตั้ง License"""
    installations_list = execute_query("""
        SELECT 
            li.installation_id, sl.software_name, sl.version, sl.license_key,
            e.equipment_code, et.type_name, e.brand, e.model,
            li.installed_date, li.uninstalled_date, li.status as installation_status
        FROM license_installations li
        JOIN software_licenses sl ON li.license_id = sl.license_id
        JOIN equipments e ON li.equipment_id = e.equipment_id
        JOIN equipment_types et ON e.type_id = et.type_id
        ORDER BY li.installed_date DESC
    """, fetch=True)
    
    return render_template('license_installations.html', installations=installations_list)


@app.route('/uninstall_license/<int:installation_id>', methods=['POST'])
def uninstall_license(installation_id):
    """ถอนการติดตั้ง License"""
    try:
        # อัพเดทสถานะการติดตั้งเป็น 'uninstalled' และบันทึกวันที่ถอนการติดตั้ง
        execute_query("""
            UPDATE license_installations 
            SET status = 'uninstalled', 
                uninstalled_date = CURRENT_DATE 
            WHERE installation_id = %s AND status = 'active'
        """, (installation_id,))
        
        flash('ถอนการติดตั้ง License เรียบร้อยแล้ว', 'success')
        
    except Exception as e:
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'error')
    
    return redirect(url_for('license_installations'))

@app.route('/license_installations/add', methods=['GET', 'POST'])
def add_license_installation():
    """เพิ่มการติดตั้ง License"""
    if request.method == 'POST':
        data = request.form

        connection = get_db_connection()
        if not connection:
            flash('เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล', 'error')
            return redirect(url_for('license_installations'))

        try:
            cursor = connection.cursor()

            # ตรวจสอบว่า License ยังมีที่ว่างไหม
            check_query = """
                SELECT max_installations, current_installations 
                FROM software_licenses WHERE license_id = %s
            """
            cursor.execute(check_query, (data['license_id'],))
            license_info = cursor.fetchone()

            if not license_info:
                flash('ไม่พบ License ที่เลือก', 'error')
                return redirect(url_for('license_installations'))

            if license_info[1] >= license_info[0]:
                flash('License นี้ถูกใช้งานครบจำนวนแล้ว', 'error')
                return redirect(url_for('license_installations'))

            # เพิ่มการติดตั้ง
            install_query = """
                INSERT INTO license_installations (license_id, equipment_id, installed_date, notes)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(install_query, (data['license_id'], data['equipment_id'], 
                                         data['installed_date'], data['notes']))

            # อัพเดทจำนวนการติดตั้งปัจจุบัน
            update_query = """
                UPDATE software_licenses 
                SET current_installations = current_installations + 1 
                WHERE license_id = %s
            """
            cursor.execute(update_query, (data['license_id'],))

            connection.commit()
            cursor.close()
            connection.close()

            flash('ติดตั้ง License สำเร็จ', 'success')

        except mysql.connector.Error as err:
            connection.rollback()
            cursor.close()
            connection.close()
            flash(f'เกิดข้อผิดพลาด: {err}', 'error')

        return redirect(url_for('license_installations'))

    # ดึงข้อมูล License และอุปกรณ์
    available_licenses = execute_query("""
        SELECT 
            sl.license_id, sl.software_name, sl.version, sl.license_key,
            sl.max_installations, sl.current_installations
        FROM software_licenses sl
        WHERE sl.current_installations < sl.max_installations AND sl.status = 'active'
        ORDER BY sl.software_name, sl.version
    """, fetch=True)

    # แก้ไข: เลือกเฉพาะอุปกรณ์ประเภท notebook
    equipments_list = execute_query("""
        SELECT 
            e.equipment_id, e.equipment_code, et.type_name, e.brand, e.model
        FROM equipments e
        JOIN equipment_types et ON e.type_id = et.type_id
        WHERE e.status IN ('available', 'assigned') 
            AND LOWER(et.type_name) = 'notebook'
        ORDER BY et.type_name, e.equipment_code
    """, fetch=True)

    return render_template('add_license_installation.html',
                         licenses=available_licenses,
                         equipments=equipments_list)

# API endpoints สำหรับ AJAX
@app.route('/api/equipment_by_employee/<int:emp_id>')
def get_equipment_by_employee(emp_id):
    """API ดึงรายการอุปกรณ์ของพนักงาน"""
    equipments = execute_query("""
        SELECT 
            e.equipment_id, e.equipment_code, et.type_name, e.brand, e.model,
            ea.assigned_date
        FROM equipment_assignments ea
        JOIN equipments e ON ea.equipment_id = e.equipment_id
        JOIN equipment_types et ON e.type_id = et.type_id
        WHERE ea.emp_id = %s AND ea.status = 'active'
        ORDER BY et.type_name, e.equipment_code
    """, (emp_id,), fetch=True)
    
    return jsonify(equipments or [])

if __name__ == '__main__':
    app.run(debug=True)