#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

DB_PATH = '/opt/reef-tracker/reef_data.db'

def init_db():
    """Initialize the database with the tanks and parameters tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create tanks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tanks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            size_gallons REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create parameters table with tank_id, water_change, and notes
    c.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tank_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            alk REAL,
            po4 REAL,
            no3 REAL,
            ca INTEGER,
            mg INTEGER,
            sg REAL,
            water_change_gallons REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tank_id) REFERENCES tanks (id) ON DELETE CASCADE,
            UNIQUE(tank_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()

def dict_factory(cursor, row):
    """Convert database row to dictionary"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# ==================== TANK ENDPOINTS ====================

@app.route('/api/tanks', methods=['GET'])
def get_tanks():
    """Get all tanks"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        c = conn.cursor()
        c.execute('SELECT id, name, size_gallons, created_at FROM tanks ORDER BY name ASC')
        data = c.fetchall()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tanks', methods=['POST'])
def add_tank():
    """Add a new tank"""
    try:
        tank = request.json
        name = tank.get('name')
        size_gallons = tank.get('size_gallons')
        
        if not name or not size_gallons:
            return jsonify({'error': 'Name and size_gallons are required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('INSERT INTO tanks (name, size_gallons) VALUES (?, ?)', 
                  (name, size_gallons))
        
        tank_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'id': tank_id}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Tank with this name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tanks/<int:tank_id>', methods=['PUT'])
def update_tank(tank_id):
    """Update a tank"""
    try:
        tank = request.json
        name = tank.get('name')
        size_gallons = tank.get('size_gallons')
        
        if not name or not size_gallons:
            return jsonify({'error': 'Name and size_gallons are required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute('UPDATE tanks SET name = ?, size_gallons = ? WHERE id = ?',
                  (name, size_gallons, tank_id))
        
        rows_updated = c.rowcount
        conn.commit()
        conn.close()
        
        if rows_updated > 0:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Tank not found'}), 404
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Tank with this name already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tanks/<int:tank_id>', methods=['DELETE'])
def delete_tank(tank_id):
    """Delete a tank and all its parameters"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM tanks WHERE id = ?', (tank_id,))
        rows_deleted = c.rowcount
        conn.commit()
        conn.close()
        
        if rows_deleted > 0:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Tank not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== PARAMETER ENDPOINTS ====================

@app.route('/api/parameters', methods=['GET'])
def get_parameters():
    """Get all parameter measurements, optionally filtered by tank_id"""
    try:
        tank_id = request.args.get('tank_id', type=int)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        c = conn.cursor()
        
        if tank_id:
            c.execute('''
                SELECT p.id, p.tank_id, p.date, p.alk, p.po4, p.no3, p.ca, p.mg, p.sg, 
                       p.water_change_gallons, p.notes, t.name as tank_name
                FROM parameters p
                JOIN tanks t ON p.tank_id = t.id
                WHERE p.tank_id = ?
                ORDER BY p.date ASC
            ''', (tank_id,))
        else:
            c.execute('''
                SELECT p.id, p.tank_id, p.date, p.alk, p.po4, p.no3, p.ca, p.mg, p.sg,
                       p.water_change_gallons, p.notes, t.name as tank_name
                FROM parameters p
                JOIN tanks t ON p.tank_id = t.id
                ORDER BY p.date ASC
            ''')
        
        data = c.fetchall()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parameters', methods=['POST'])
def add_parameter():
    """Add or update a parameter measurement"""
    try:
        entry = request.json
        tank_id = entry.get('tank_id')
        date = entry.get('date')
        
        if not tank_id or not date:
            return jsonify({'error': 'tank_id and date are required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Verify tank exists
        c.execute('SELECT id FROM tanks WHERE id = ?', (tank_id,))
        if not c.fetchone():
            conn.close()
            return jsonify({'error': 'Tank not found'}), 404
        
        # Upsert: insert or replace if tank_id + date exists
        c.execute('''
            INSERT OR REPLACE INTO parameters 
            (tank_id, date, alk, po4, no3, ca, mg, sg, water_change_gallons, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tank_id,
            date,
            entry.get('alk'),
            entry.get('po4'),
            entry.get('no3'),
            entry.get('ca'),
            entry.get('mg'),
            entry.get('sg'),
            entry.get('water_change_gallons'),
            entry.get('notes')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'date': date}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parameters/<int:param_id>', methods=['DELETE'])
def delete_parameter(param_id):
    """Delete a specific parameter measurement by id"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM parameters WHERE id = ?', (param_id,))
        conn.commit()
        rows_deleted = c.rowcount
        conn.close()
        
        if rows_deleted > 0:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Entry not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parameters/clear', methods=['DELETE'])
def clear_all():
    """Clear all parameter measurements for a specific tank"""
    try:
        tank_id = request.args.get('tank_id', type=int)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        if tank_id:
            c.execute('DELETE FROM parameters WHERE tank_id = ?', (tank_id,))
        else:
            c.execute('DELETE FROM parameters')
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Data cleared'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ANALYTICS ENDPOINTS ====================

@app.route('/api/analytics/water-change-monthly', methods=['GET'])
def get_monthly_water_change():
    """Calculate monthly water change percentage for a tank"""
    try:
        tank_id = request.args.get('tank_id', type=int)
        
        if not tank_id:
            return jsonify({'error': 'tank_id is required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        c = conn.cursor()
        
        # Get tank size
        c.execute('SELECT size_gallons FROM tanks WHERE id = ?', (tank_id,))
        tank = c.fetchone()
        if not tank:
            conn.close()
            return jsonify({'error': 'Tank not found'}), 404
        
        tank_size = tank['size_gallons']
        
        # Calculate monthly totals for the last 12 months
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        c.execute('''
            SELECT 
                strftime('%Y-%m', date) as month,
                SUM(water_change_gallons) as total_gallons
            FROM parameters
            WHERE tank_id = ? AND water_change_gallons IS NOT NULL
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        ''', (tank_id,))
        
        monthly_data = c.fetchall()
        
        # Calculate current month total
        c.execute('''
            SELECT SUM(water_change_gallons) as total_gallons
            FROM parameters
            WHERE tank_id = ? 
            AND date >= ?
            AND water_change_gallons IS NOT NULL
        ''', (tank_id, thirty_days_ago))
        
        last_30_days = c.fetchone()
        
        conn.close()
        
        # Calculate percentages
        for row in monthly_data:
            if row['total_gallons']:
                row['percentage'] = round((row['total_gallons'] / tank_size) * 100, 1)
            else:
                row['percentage'] = 0
        
        last_30_days_percentage = 0
        if last_30_days and last_30_days['total_gallons']:
            last_30_days_percentage = round((last_30_days['total_gallons'] / tank_size) * 100, 1)
        
        return jsonify({
            'tank_size': tank_size,
            'last_30_days': {
                'gallons': last_30_days['total_gallons'] if last_30_days else 0,
                'percentage': last_30_days_percentage
            },
            'monthly_history': monthly_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    # Run on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
