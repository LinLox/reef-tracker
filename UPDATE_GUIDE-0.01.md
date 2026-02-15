# Reef Tracker - Update Guide (Multi-Tank Support)

## Overview
This update adds support for:
- **Multiple tanks** - Track parameters for multiple reef tanks separately
- **Water change tracking** - Log water changes in gallons and view monthly percentage statistics
- **Maintenance notes** - Add notes/comments to each entry for maintenance tracking

## Database Changes

The new version uses a different database schema. You have two options:

### Option 1: Fresh Start (Recommended for Testing)
Start with a clean database to test the new features.

### Option 2: Migration (Keep Existing Data)
Migrate your existing data to the new schema.

---

## Update Instructions

### Step 1: Backup Your Current Database

**IMPORTANT:** Always backup before making changes!

```bash
ssh root@<container-ip>
cd /opt/reef-tracker
cp reef_data.db reef_data.db.backup-$(date +%Y%m%d)
```

### Step 2: Stop the API Service

```bash
systemctl stop reef-tracker-api
```

### Step 3: Update the API Code

Replace the old `api.py` with the new version:

```bash
cd /opt/reef-tracker
nano api.py
```

Delete the old content and paste the new `api.py` code, then save (Ctrl+X, Y, Enter).

### Step 4: Update the Frontend

Update the HTML file:

```bash
cd /var/www/reef-tracker
nano index.html
```

Delete the old content and paste the new `index.html` code, then save.

### Step 5: Choose Your Database Strategy

#### Option A: Fresh Start (Clean Database)

If you want to start fresh:

```bash
cd /opt/reef-tracker
rm reef_data.db  # Remove old database
# The new database will be created automatically when you start the API
```

#### Option B: Migrate Existing Data

If you want to keep your existing data, create this migration script:

```bash
nano /opt/reef-tracker/migrate_db.py
```

Paste this migration script:

```python
#!/usr/bin/env python3
import sqlite3
import sys

OLD_DB = 'reef_data.db.backup'  # Your backup
NEW_DB = 'reef_data.db'
DEFAULT_TANK_NAME = 'Main Tank'
DEFAULT_TANK_SIZE = 75  # Change this to your actual tank size in gallons

def migrate():
    # Connect to both databases
    old_conn = sqlite3.connect(OLD_DB)
    new_conn = sqlite3.connect(NEW_DB)
    
    old_c = old_conn.cursor()
    new_c = new_conn.cursor()
    
    print("Creating new schema...")
    
    # Create new tables
    new_c.execute('''
        CREATE TABLE IF NOT EXISTS tanks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            size_gallons REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    new_c.execute('''
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
    
    print(f"Creating default tank: '{DEFAULT_TANK_NAME}' ({DEFAULT_TANK_SIZE} gallons)")
    
    # Create a default tank
    new_c.execute('INSERT INTO tanks (name, size_gallons) VALUES (?, ?)',
                  (DEFAULT_TANK_NAME, DEFAULT_TANK_SIZE))
    tank_id = new_c.lastrowid
    
    print("Migrating parameter data...")
    
    # Migrate old parameters to new structure
    old_c.execute('SELECT date, alk, po4, no3, ca, mg, sg FROM parameters ORDER BY date')
    old_data = old_c.fetchall()
    
    count = 0
    for row in old_data:
        new_c.execute('''
            INSERT INTO parameters (tank_id, date, alk, po4, no3, ca, mg, sg, water_change_gallons, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        ''', (tank_id, *row))
        count += 1
    
    new_conn.commit()
    
    print(f"Migration complete! Migrated {count} parameter entries.")
    print(f"All data assigned to tank: '{DEFAULT_TANK_NAME}'")
    
    old_conn.close()
    new_conn.close()

if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
```

Save and exit, then make it executable and run it:

```bash
chmod +x migrate_db.py

# IMPORTANT: Edit the script first to set your actual tank size!
nano migrate_db.py
# Change DEFAULT_TANK_SIZE = 75 to your actual tank size

# Run the migration
source venv/bin/activate
python3 migrate_db.py
```

### Step 6: Start the API Service

```bash
systemctl start reef-tracker-api
systemctl status reef-tracker-api
```

Verify it's running properly. Check for any errors:

```bash
journalctl -u reef-tracker-api -f
```

### Step 7: Test the Application

1. Open your browser and go to `https://reef.yourdomain.com`
2. You should see the new tank management interface
3. If you migrated data, you should see your default tank with all your existing parameters
4. Try adding a new tank
5. Try adding a measurement with a water change and notes

---

## New Features Guide

### Managing Tanks

1. **Add a tank**: Fill in the "Tank Name" and "Size (gallons)" fields, then click "Add Tank"
2. **Delete a tank**: Click the "Delete" button next to a tank (this will delete ALL data for that tank)
3. **Select a tank**: Use the dropdown to select which tank you want to work with

### Adding Measurements with New Fields

1. **Select your tank** from the dropdown
2. Fill in the date and any parameters you measured
3. **Water Change**: Enter the amount of water changed in gallons (optional)
4. **Notes**: Add any maintenance notes, observations, or comments (optional)
5. Click "Add / Update Entry"

### Water Change Statistics

When you select a tank, you'll see a blue box showing:
- **Monthly Water Change Percent**: The percentage of your tank volume that was changed in the last 30 days
- This helps you track if you're doing enough water changes

Example: If you have a 75-gallon tank and changed 20 gallons in the last 30 days, it will show "26.7% water changed in last 30 days"

### Viewing Data

- **Charts**: All parameters are still charted as before (water changes are NOT charted)
- **Data Log Table**: Now includes columns for water change amount and notes
- **Notes column**: Hover over truncated notes to see the full text

---

## Troubleshooting

### API won't start after update

Check the logs:
```bash
journalctl -u reef-tracker-api -n 50
```

Common issues:
- Database schema error: Make sure you either migrated properly or started with a fresh database
- Python dependencies: Make sure flask and flask-cors are installed in the venv

### Frontend shows "Failed to load tanks"

1. Check if the API is running: `systemctl status reef-tracker-api`
2. Test the API directly: `curl http://localhost:5000/api/tanks`
3. Check nginx is proxying correctly: `nginx -t`

### Migration failed

1. Make sure you have a backup: `ls -la /opt/reef-tracker/*.backup*`
2. Restore from backup: `cp reef_data.db.backup reef_data.db`
3. Try the migration again or start fresh

### Data not showing after migration

1. Check if the migration script ran successfully
2. Verify the data is in the new database:
   ```bash
   sqlite3 /opt/reef-tracker/reef_data.db
   SELECT * FROM tanks;
   SELECT COUNT(*) FROM parameters;
   .quit
   ```

---

## Rolling Back

If you need to go back to the old version:

```bash
# Stop the service
systemctl stop reef-tracker-api

# Restore old database
cd /opt/reef-tracker
cp reef_data.db.backup reef_data.db

# Restore old API code (you'll need to have saved it)
# Or reinstall from your original setup

# Restore old HTML
cd /var/www/reef-tracker
# Restore your backup of the old index.html

# Restart
systemctl start reef-tracker-api
```

---

## Database Backup Automation (Recommended)

Create a daily backup script:

```bash
nano /opt/reef-tracker/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/reef-tracker/backups"
mkdir -p $BACKUP_DIR

# Keep last 30 days of backups
cp /opt/reef-tracker/reef_data.db "$BACKUP_DIR/reef_data.db.$(date +%Y%m%d)"
find $BACKUP_DIR -name "reef_data.db.*" -mtime +30 -delete
```

```bash
chmod +x /opt/reef-tracker/backup.sh

# Add to crontab (runs daily at 2 AM)
crontab -e
# Add this line:
0 2 * * * /opt/reef-tracker/backup.sh
```

---

## Support

If you run into issues:

1. Check the API logs: `journalctl -u reef-tracker-api -f`
2. Check nginx error logs: `tail -f /var/log/nginx/error.log`
3. Test the API endpoints directly with curl
4. Make sure you have backups before making changes

## Summary of Changes

**Backend (api.py):**
- New `tanks` table for managing multiple tanks
- Updated `parameters` table with `tank_id`, `water_change_gallons`, and `notes` fields
- New endpoints: `/api/tanks` (GET, POST, PUT, DELETE)
- New endpoint: `/api/analytics/water-change-monthly` for statistics
- Updated parameter endpoints to filter by tank

**Frontend (index.html):**
- Tank management UI (add/delete tanks)
- Tank selector dropdown
- Water change input field
- Notes textarea
- Monthly water change percentage display
- Updated data table with new columns
- All charts now filter by selected tank
