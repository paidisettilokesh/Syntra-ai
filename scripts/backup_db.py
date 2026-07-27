import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    db_path_str = os.getenv("DB_NAME", "data/agent_logs.db")
    db_path = Path(db_path_str)
    
    if not db_path.exists():
        print(f"Backup failed: Source database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)
        
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"agent_logs_backup_{timestamp}.db"
    
    try:
        src_conn = sqlite3.connect(str(db_path))
        dst_conn = sqlite3.connect(str(backup_path))
        
        with dst_conn:
            src_conn.backup(dst_conn, pages=10, progress=None)
            
        dst_conn.close()
        src_conn.close()
        print(f"Backup succeeded: Database copied to {backup_path}")
        sys.exit(0)
    except Exception as e:
        print(f"Backup failed with error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
