import sqlite3

conn = sqlite3.connect('equipment.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT,
    status TEXT DEFAULT 'Исправно',
    location TEXT,
    temperature REAL,
    cpu INTEGER,
    memory REAL,
    network REAL,
    response REAL,
    last_update TEXT
)
''')

conn.commit()
conn.close()
