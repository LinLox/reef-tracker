# Reef Tracker - Proxmox LXC Setup Guide
Put together using beginner knowledge of coding and AI as a learning project to see how everything comes together in an isolated LAN.

## Overview
This guide will help you set up your reef tank parameter tracker on an Ubuntu LXC container in Proxmox, with a Python/Flask backend and SQLite database.

## Step 1: Create Ubuntu LXC Container in Proxmox

1. In Proxmox web UI, click "Create CT"
2. Choose Ubuntu 22.04 or 24.04 template
3. Set hostname (e.g., `reef-tracker`)
4. Set a static IP or DHCP (I recommend static for ease of use with nginx proxy manager)
5. Allocate resources:
   - Disk: 8GB is plenty
   - CPU: 1 core
   - RAM: 512MB-1GB
6. Create and start the container

## Step 2: Initial Container Setup

SSH into your new container:
```bash
ssh root@<container-ip>
```

Update the system:
```bash
apt update && apt upgrade -y
```

## Step 3: Install Python, SQLite, and Dependencies

Install Python 3, pip, and SQLite:
```bash
apt install -y python3 python3-pip python3-venv sqlite3
```

Create a directory for your application:
```bash
mkdir -p /opt/reef-tracker
cd /opt/reef-tracker
```

Create a Python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install Flask (lightweight Python web framework):
```bash
pip install flask flask-cors
```

## Step 4: Create the Python Backend API

Create the API file:
```bash
nano /opt/reef-tracker/api.py
```

Paste this code:

```python
#!/usr/bin/env python3
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

DB_PATH = '/opt/reef-tracker/reef_data.db'

def init_db():
    """Initialize the database with the parameters table"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            date TEXT PRIMARY KEY,
            alk REAL,
            po4 REAL,
            no3 REAL,
            ca INTEGER,
            mg INTEGER,
            sg REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

@app.route('/api/parameters', methods=['GET'])
def get_parameters():
    """Get all parameter measurements"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        c = conn.cursor()
        c.execute('SELECT date, alk, po4, no3, ca, mg, sg FROM parameters ORDER BY date ASC')
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
        date = entry.get('date')
        
        if not date:
            return jsonify({'error': 'Date is required'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Upsert: insert or replace if date exists
        c.execute('''
            INSERT OR REPLACE INTO parameters 
            (date, alk, po4, no3, ca, mg, sg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            date,
            entry.get('alk'),
            entry.get('po4'),
            entry.get('no3'),
            entry.get('ca'),
            entry.get('mg'),
            entry.get('sg')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'date': date}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parameters/<date>', methods=['DELETE'])
def delete_parameter(date):
    """Delete a specific parameter measurement by date"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM parameters WHERE date = ?', (date,))
        conn.commit()
        rows_deleted = c.rowcount
        conn.close()
        
        if rows_deleted > 0:
            return jsonify({'success': True, 'deleted': date}), 200
        else:
            return jsonify({'error': 'Date not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/parameters/clear', methods=['DELETE'])
def clear_all():
    """Clear all parameter measurements"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM parameters')
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'All data cleared'}), 200
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
```

Save and exit (Ctrl+X, Y, Enter)

Make it executable:
```bash
chmod +x /opt/reef-tracker/api.py
```

## Step 5: Test the API

Initialize the database and start the API:
```bash
cd /opt/reef-tracker
source venv/bin/activate
python3 api.py
```

You should see:
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```

Press Ctrl+C to stop it for now.

## Step 6: Create a Systemd Service (Run API Automatically)

Create a service file:
```bash
nano /etc/systemd/system/reef-tracker-api.service
```

Paste this:
```ini
[Unit]
Description=Reef Tracker API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/reef-tracker
Environment="PATH=/opt/reef-tracker/venv/bin"
ExecStart=/opt/reef-tracker/venv/bin/python3 /opt/reef-tracker/api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save and exit.

Enable and start the service:
```bash
systemctl daemon-reload
systemctl enable reef-tracker-api
systemctl start reef-tracker-api
```

Check if it's running:
```bash
systemctl status reef-tracker-api
```

You should see "active (running)" in green.

## Step 7: Install and Configure Nginx

Install nginx:
```bash
apt install -y nginx
```

Download Chart.js library (needed by your HTML):
```bash
mkdir -p /var/www/reef-tracker
cd /var/www/reef-tracker
curl -o chart.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
```

Upload your HTML file:
```bash
nano /var/www/reef-tracker/index.html
```

Paste your index.html content here.

Save and exit.

Create nginx configuration:
```bash
nano /etc/nginx/sites-available/reef-tracker
```

Paste this:
```nginx
server {
    listen 80;
    server_name _;
    
    root /var/www/reef-tracker;
    index index.html;
    
    # Serve static files
    location / {
        try_files $uri $uri/ =404;
    }
    
    # Proxy API requests to Flask backend
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Save and exit.

Enable the site:
```bash
ln -s /etc/nginx/sites-available/reef-tracker /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site
nginx -t  # Test configuration
systemctl restart nginx
```

## Step 8: Configure Nginx Proxy Manager

In your nginx proxy manager:

1. Add a new Proxy Host
2. Domain Names: `reef.yourdomain.com` (or whatever subdomain you want)
3. Scheme: `http`
4. Forward Hostname/IP: `<your-lxc-container-ip>`
5. Forward Port: `80`
6. Enable "Websockets Support" (optional but good practice)
7. SSL tab: Select your wildcard certificate
8. Force SSL: Yes

## Step 9: Configure AdGuard/Unbound DNS

Add a DNS rewrite rule in AdGuard Home:
- Domain: `reef.yourdomain.com`
- IP: Your nginx proxy manager IP

## Step 10: Test Everything

1. Visit `https://reef.yourdomain.com` in your browser
2. You should see the reef tracker interface
3. Try adding a test measurement
4. Check if the chart updates
5. Check the raw data table

## Troubleshooting

### API not responding
```bash
systemctl status reef-tracker-api
journalctl -u reef-tracker-api -f  # View live logs
```

### Check if API is listening
```bash
netstat -tlnp | grep 5000
```

### Test API directly
```bash
curl http://localhost:5000/health
curl http://localhost:5000/api/parameters
```

### Nginx errors
```bash
nginx -t  # Test configuration
tail -f /var/log/nginx/error.log
```

### Database location
The SQLite database is stored at: `/opt/reef-tracker/reef_data.db`

To back it up:
```bash
cp /opt/reef-tracker/reef_data.db /opt/reef-tracker/reef_data.db.backup
```

## Optional: Enable Firewall

If you want to restrict access:
```bash
apt install -y ufw
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw enable
```
