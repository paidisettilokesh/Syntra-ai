import sys
import os
import sqlite3
import shutil
from pathlib import Path
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    if len(sys.argv) < 2:
        print("Usage: python restore_db.py <path_to_backup_file>", file=sys.stderr)
        sys.exit(1)
        
    backup_path = Path(sys.argv[1])
    if not backup_path.exists():
        print(f"Restore failed: Backup file not found at {backup_path}", file=sys.stderr)
        sys.exit(1)
        
    db_path_str = os.getenv("DB_NAME", "data/agent_logs.db")
    db_path = Path(db_path_str)
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Restore failed: Backup file is not a valid SQLite database: {e}", file=sys.stderr)
        sys.exit(1)
        
    if db_path.exists():
        safety_backup = db_path.with_name(f"{db_path.name}.safety_backup")
        try:
            shutil.copy2(db_path, safety_backup)
            print(f"Safety backup created at {safety_backup}")
        except Exception as e:
            print(f"Warning: Could not create safety backup of current database: {e}", file=sys.stderr)
            
    try:
        src_conn = sqlite3.connect(str(backup_path))
        dst_conn = sqlite3.connect(str(db_path))
        with dst_conn:
            src_conn.backup(dst_conn, pages=10, progress=None)
        dst_conn.close()
        src_conn.close()
        print(f"Restore succeeded: Restored database from {backup_path}")
        sys.exit(0)
    except Exception as e:
        print(f"Restore failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
