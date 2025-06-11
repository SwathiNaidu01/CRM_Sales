def create_database():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create dashboard table (already in your code)
    c.execute("PRAGMA table_info(dashboard)")
    dashboard_columns = [col[1] for col in c.fetchall()]

    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]

    if 'dashboard' not in tables or 'created_at' not in dashboard_columns:
        c.execute('DROP TABLE IF EXISTS dashboard')
        c.execute('''
            CREATE TABLE dashboard (
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_emp_name ON dashboard (emp_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_client_name ON dashboard (client_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON dashboard (status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_report_date ON dashboard (report_date)')
        print("Dashboard table created with current schema")
    else:
        print("Dashboard table already exists with correct schema")

    # Create users table if not exists
    if 'users' not in tables:
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ('testuser', 'testpass'))
        print("Users table created and default user added")
    else:
        print("Users table already exists")

    conn.commit()
    conn.close()
