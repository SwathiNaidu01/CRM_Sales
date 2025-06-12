from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
import sqlite3
import os
import pandas as pd
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "Swathi@01"
app.config['PER_PAGE'] = 20
DB_FILE = 'data.db'

# ------------------ UTILITY FUNCTIONS ------------------ #

def create_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS dashboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_name TEXT,
            role TEXT,
            department TEXT,
            client_name TEXT,
            client_email TEXT,
            report_date TEXT,
            feedback TEXT,
            follow_up_date TEXT,
            notes TEXT,
            budget REAL,
            status TEXT,
            project_name TEXT,
            contact_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT CHECK(role IN ('admin', 'user')),
            emp_name TEXT
        )
    ''')
    
    # Create indexes for efficient filtering
    c.execute('CREATE INDEX IF NOT EXISTS idx_emp_name ON dashboard (emp_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_client_name ON dashboard (client_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_status ON dashboard (status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_report_date ON dashboard (report_date)')
    
    # Add default admin user if not exists
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role, emp_name) VALUES (?, ?, ?, ?)",
                 ('admin', 'admin123', 'admin', 'Admin'))
    
   

    conn.commit()
    conn.close()

def get_status_options():
    """Fetches distinct status options from the dashboard table."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT status FROM dashboard WHERE status IS NOT NULL AND status != '' ORDER BY status")
    options = [row['status'] for row in cur.fetchall()]
    conn.close()
    if not options:
        # Provide default options if no statuses are found in the database
        options = ['In Progress', 'Completed', 'Pending', 'On Hold']
    return options

create_database() # Initialize database and default admin user on app startup

# ------------------ AUTHENTICATION ROUTES ------------------ #

@app.route('/')
def index():
    """Redirects to the login page."""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and user['password'] == password: # Basic password check
            session['username'] = username
            session['logged_in'] = True
            session['role'] = user['role']
            session['emp_name'] = user['emp_name'] # Store emp_name in session
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the current user."""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# ------------------ DASHBOARD PAGES ------------------ #


@app.route('/home')
def home():
    """Displays the main dashboard overview."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Fetch general statistics
    c.execute("SELECT COUNT(*) FROM dashboard")
    total_projects = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM dashboard WHERE status = 'Completed'")
    completed_projects = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM dashboard WHERE status = 'In Progress'")
    in_progress_projects = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM dashboard WHERE status = 'Pending'")
    pending_projects = c.fetchone()[0]
    
    # Fetch recent activity, potentially filtered by user if not admin
    if session.get('role') == 'admin':
        c.execute("SELECT project_name, client_name, status, updated_at FROM dashboard ORDER BY updated_at DESC LIMIT 5")
    else:
        c.execute("SELECT project_name, client_name, status, updated_at FROM dashboard WHERE emp_name = ? ORDER BY updated_at DESC LIMIT 5", (session['emp_name'],))
    recent_activity = c.fetchall()
    
    conn.close()
    
    return render_template('home.html', 
                         username=session['username'],
                         total_projects=total_projects,
                         completed_projects=completed_projects,
                         in_progress_projects=in_progress_projects,
                         pending_projects=pending_projects,
                         recent_activity=recent_activity,
                         is_admin=(session.get('role') == 'admin'))  # Pass is_admin flag

@app.route('/new_dashboard', methods=['GET', 'POST'])
def new_dashboard():
    """Handles creation of new dashboard entries."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = request.form

        try:
            budget = float(data.get('budget', 0))
        except ValueError:
            budget = 0.0
            flash('Invalid budget value', 'danger')

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # --- IMPORTANT CHANGE HERE ---
        # Automatically set emp_name from session for non-admin users,
        # or allow admin to set it manually.
        if session.get('role') == 'user':
            emp_name_for_entry = session['emp_name']
        else: # Admin can specify or it comes from the form for admin
            emp_name_for_entry = data['emp_name']
        # --- END IMPORTANT CHANGE ---

        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''
                INSERT INTO dashboard (
                    emp_name, role, department, client_name, client_email,
                    report_date, feedback, follow_up_date, notes,
                    budget, status, project_name, contact_number,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                emp_name_for_entry, data['role'], data['department'],
                data['client_name'], data['client_email'],
                data['report_date'], data.get('feedback', ''),
                data.get('follow_up_date', ''), data.get('notes', ''),
                budget, data['status'], data['project_name'],
                data['contact_number'], now, now
            ))
            conn.commit()
            flash('Entry created successfully!', 'success')
            return redirect(url_for('dashboard_entries'))
        except Exception as e:
            if conn:
                conn.rollback()
            flash(f'Error creating entry: {str(e)}', 'danger')
        finally:
            if conn:
                conn.close()

    # For GET request, pass emp_name from session to pre-fill the form
    return render_template('new_dashboard.html',
                            status_options=get_status_options(),
                            session_emp_name=session.get('emp_name'), # Pass emp_name for pre-filling
                            session_role=session.get('role', '')) # Pass role for conditional rendering

@app.route('/dashboard_entries')
def dashboard_entries():
    """Displays all dashboard entries with filtering options."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get filter parameters from request
    emp_name_filter = request.args.get('emp_name', '').strip()
    client_name_filter = request.args.get('client_name', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Base query
    query = "SELECT * FROM dashboard WHERE 1=1"
    params = []
    
    # Apply filters
    if emp_name_filter:
        query += " AND emp_name LIKE ?"
        params.append(f"%{emp_name_filter}%")
    
    if client_name_filter:
        query += " AND client_name LIKE ?"
        params.append(f"%{client_name_filter}%")
    
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    
    # For regular users, only show their entries
    if session.get('role') == 'user':
        query += " AND emp_name = ?"
        params.append(session['emp_name'])
    
    query += " ORDER BY updated_at DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return render_template('dashboard_entries.html',
                         rows=rows,
                         status_options=get_status_options(),
                         filters={
                             'emp_name': emp_name_filter,
                             'client_name': client_name_filter,
                             'status': status_filter
                         },
                         is_admin=(session.get('role') == 'admin'))

@app.route('/edit_entry/<int:id>', methods=['GET', 'POST'])
def edit_entry(id):
    """Allows viewing/editing of a specific dashboard entry."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM dashboard WHERE id = ?', (id,))
    entry = c.fetchone()
    conn.close()
    
    if not entry:
        flash("Entry not found", "danger")
        return redirect(url_for('dashboard_entries'))
    
    # Check permissions
    is_owner = (session.get('emp_name') == entry['emp_name'])
    is_admin = (session.get('role') == 'admin')
    
    if not is_admin and not is_owner:
        flash("You don't have permission to access this entry", "danger")
        return redirect(url_for('dashboard_entries'))
    
    if request.method == 'GET':
        # For GET requests, just show the entry
        return render_template('view_entry.html', 
                            entry=entry,
                            can_edit=(is_owner or is_admin),
                            is_admin=is_admin)
    
    elif request.method == 'POST':
        # For POST requests, handle the update
        if not (is_owner or is_admin):
            flash("You don't have permission to edit this entry", "danger")
            return redirect(url_for('dashboard_entries'))
        
        data = request.form
        try:
            budget = float(data.get('budget', 0))
        except ValueError:
            budget = 0.0
            flash('Invalid budget value', 'danger')
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''
                UPDATE dashboard SET
                    emp_name = ?, role = ?, department = ?, client_name = ?, client_email = ?,
                    report_date = ?, feedback = ?, follow_up_date = ?, notes = ?,
                    budget = ?, status = ?, project_name = ?, contact_number = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (
                data['emp_name'], data['role'], data['department'], 
                data['client_name'], data['client_email'], 
                data['report_date'], data.get('feedback', ''),
                data.get('follow_up_date', ''), data.get('notes', ''),
                budget, data['status'], data['project_name'], 
                data['contact_number'], now, id
            ))
            conn.commit()
            flash('Entry updated successfully!', 'success')
            return redirect(url_for('dashboard_entries'))
        except Exception as e:
            conn.rollback()
            flash(f'Error updating entry: {str(e)}', 'danger')
            return redirect(url_for('edit_entry', id=id))
        finally:
            if conn:
                conn.close()



    
@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    """Deletes a dashboard entry. Accessible only by admins."""
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('home'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute('DELETE FROM dashboard WHERE id = ?', (entry_id,))
        conn.commit()
        flash('Entry deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting entry: {str(e)}', 'danger')
    finally:
        conn.close()
    return redirect(url_for('dashboard_entries'))
    

@app.route('/manages', methods=['GET', 'POST'])
def manage_users():
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username').strip()
        emp_name = request.form.get('emp_name').strip()

        # Fixed values
        password = "user123"
        role = "user"

        if not username or not emp_name:
            flash("All fields are required", "danger")
        else:
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password, role, emp_name) VALUES (?, ?, ?, ?)",
                          (username, password, role, emp_name))
                conn.commit()
                flash(f"User '{username}' added with default password 'user123'", "success")
            except sqlite3.IntegrityError:
                flash("Username already exists", "danger")
            finally:
                conn.close()

    # Get all users for display
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, username, role, emp_name FROM users")
    users = c.fetchall()
    conn.close()

    return render_template('manages.html', users=users)

    
    # Get all users for display
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, username, role, emp_name FROM users") # Exclude password for security
    users = c.fetchall()
    conn.close()
    
    return render_template('manages.html', users=users)

@app.route('/change_credentials', methods=['GET', 'POST'])
def change_credentials():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    current_username = session['username']

    if request.method == 'POST':
        new_username = request.form.get('new_username').strip()
        new_password = request.form.get('new_password').strip()

        if not new_username or not new_password:
            flash("Username and password cannot be empty", "danger")
            return redirect(url_for('change_credentials'))

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        try:
            # Ensure the new username isn't taken (unless it's their own)
            c.execute("SELECT id FROM users WHERE username = ? AND username != ?", (new_username, current_username))
            if c.fetchone():
                flash("Username already taken", "danger")
                return redirect(url_for('change_credentials'))

            c.execute("UPDATE users SET username = ?, password = ? WHERE username = ?",
                      (new_username, new_password, current_username))
            conn.commit()

            session['username'] = new_username  # update session
            flash("Credentials updated successfully", "success")
        except Exception as e:
            flash(f"Error updating credentials: {str(e)}", "danger")
        finally:
            conn.close()

        return redirect(url_for('home'))

    return render_template('change_credentials.html', username=current_username)

@app.route('/download_excel')
def download_excel():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    print("===> Excel Download Triggered by:", session.get('username'))

    filters = {k: v.strip() for k, v in request.args.items()}
    print("===> Filters received:", filters)

    conn = sqlite3.connect(DB_FILE)
    query = "SELECT * FROM dashboard WHERE 1=1"
    params = []

    if session.get('role') == 'user':
        query += " AND emp_name = ?"
        params.append(session['emp_name'])

    if filters.get('emp_name'):
        query += " AND emp_name LIKE ?"
        params.append(f"%{filters['emp_name']}%")

    # Add client_name_filter
    if filters.get('client_name'):
        query += " AND client_name LIKE ?"
        params.append(f"%{filters['client_name']}%")

    # Add status_filter
    if filters.get('status'):
        query += " AND status = ?"
        params.append(filters['status'])

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    print("===> DataFrame shape:", df.shape)

    if df.empty:
        flash("No data available to download.", "warning")
        return redirect(url_for('dashboard_entries'))

    output = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dashboard_export_{timestamp}.xlsx"

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dashboard')

    output.seek(0)

    print("===> Excel file created and ready to download.")

    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    """Handles adding new employees (admin only)"""
    if not session.get('logged_in') or session.get('role') != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        emp_name = request.form.get('emp_name').strip()
        username = request.form.get('username').strip()
        temp_password = request.form.get('temp_password').strip()
        
        if not all([emp_name, username, temp_password]):
            flash("All fields are required", "danger")
        else:
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password, role, emp_name) VALUES (?, ?, ?, ?)",
                         (username, temp_password, 'user', emp_name))
                conn.commit()
                flash(f"Employee '{emp_name}' added successfully!", 'success')
                return redirect(url_for('home'))
            except sqlite3.IntegrityError:
                flash("Username already exists", "danger")
            except Exception as e:
                flash(f"Error adding employee: {str(e)}", "danger")
            finally:
                if conn:
                    conn.close()
    
    return render_template('add_employee.html')

    
if __name__ == '__main__':
    app.run(debug=True)
