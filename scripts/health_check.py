import sys
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    db_path_str = os.getenv("DB_NAME", "data/agent_logs.db")
    db_path = Path(db_path_str)
    
    if not db_path.exists():
        print(f"Healthcheck failed: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_emails';")
        res = cursor.fetchone()
        conn.close()
        if not res:
            print("Healthcheck failed: processed_emails table not found", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Healthcheck failed: SQLite connection/query error: {e}", file=sys.stderr)
        sys.exit(1)
        
    log_path_str = os.getenv("LOG_FILE", "logs/agent.log")
    log_dir = Path(log_path_str).parent
    if not log_dir.exists():
        print(f"Healthcheck failed: Log directory not found at {log_dir}", file=sys.stderr)
        sys.exit(1)
    if not os.access(log_dir, os.W_OK):
        print(f"Healthcheck failed: Log directory {log_dir} is not writable", file=sys.stderr)
        sys.exit(1)
        
    print("Healthcheck passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
