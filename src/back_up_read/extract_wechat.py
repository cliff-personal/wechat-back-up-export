import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# Default iOS Backup path on macOS
SYSTEM_BACKUP_ROOT = Path.home() / "Library/Application Support/MobileSync/Backup"
DOWNLOADS_BACKUP_ROOT = Path.home() / "Downloads"

def list_backups():
    candidates = []
    
    # Check System Backup Path
    if SYSTEM_BACKUP_ROOT.exists():
        try:
            for d in SYSTEM_BACKUP_ROOT.iterdir():
                if d.is_dir() and (d / "Manifest.db").exists():
                    candidates.append(d)
        except PermissionError:
            print(f"[Permission Denied] Cannot access {SYSTEM_BACKUP_ROOT}.")
    
    # Check Downloads
    if DOWNLOADS_BACKUP_ROOT.exists():
        for d in DOWNLOADS_BACKUP_ROOT.iterdir():
            if d.is_dir() and (d / "Manifest.db").exists():
                candidates.append(d)

    backups_with_time = []
    for d in candidates:
        try:
            mtime = datetime.fromtimestamp(d.stat().st_mtime)
            backups_with_time.append((d, mtime))
        except OSError:
            pass
            
    backups_with_time.sort(key=lambda x: x[1], reverse=True)
    return backups_with_time

def extract_from_backup(backup_path: Path, output_dir: Path, extract_audio: bool = False):
    manifest_db = backup_path / "Manifest.db"
    if not manifest_db.exists():
        print(f"Manifest.db not found in {backup_path}")
        return

    print(f"Reading Manifest from: {backup_path.name}")
    print(f"Time: {datetime.fromtimestamp(backup_path.stat().st_mtime)}")
    
    try:
        conn = sqlite3.connect(manifest_db)
        cursor = conn.cursor()
    except sqlite3.DatabaseError as e:
        print(f"Error opening Manifest.db: {e}")
        return

    domain = 'AppDomain-com.tencent.xin'
    
    # 1. Extract Databases (MM.sqlite, WCDB_Contact.sqlite, message_*.sqlite)
    print("Scanning for WeChat databases (MM.sqlite, WCDB, message_*.sqlite)...")
    cursor.execute(
        "SELECT fileID, relativePath FROM Files WHERE domain=? AND (relativePath LIKE '%MM.sqlite' OR relativePath LIKE '%WCDB_Contact.sqlite' OR relativePath LIKE '%message_%.sqlite')", 
        (domain,)
    )
    db_rows = cursor.fetchall()
    
    for file_id, rel_path in db_rows:
        # Structure usually: Documents/HASH/DB/FILENAME
        p = Path(rel_path)
        parts = p.parts
        user_hash = "unknown"
        
        # Try to find user hash from path (usually parent of DB folder or similar)
        # Standard: Documents/[32-char-hash]/DB/file.sqlite
        if "DB" in parts:
            idx = parts.index("DB")
            if idx > 0:
                user_hash = parts[idx-1]
        elif len(parts) >= 3 and parts[0] == "Documents":
             # Fallback: Documents/HASH/file.sqlite
             user_hash = parts[1]
        
        print(f"Found DB: {p.name} for user: {user_hash}")
        
        file_hash = file_id
        shard = file_hash[:2]
        source_file = backup_path / shard / file_hash
        
        target_dir = output_dir / user_hash
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / p.name
        
        if source_file.exists():
            shutil.copy2(source_file, target_file)
            print(f"  -> Extracted to {target_file}")
        else:
            print(f"  -> Source file missing in backup: {file_hash}")

    # 2. Extract Audio (Optional)
    if extract_audio:
        print("Scanning for Audio (.aud)...")
        cursor.execute(
            "SELECT fileID, relativePath FROM Files WHERE domain=? AND relativePath LIKE '%.aud'", 
            (domain,)
        )
        audio_rows = cursor.fetchall()
        print(f"Found {len(audio_rows)} audio files.")
        
        for file_id, rel_path in audio_rows:
            p = Path(rel_path)
            parts = p.parts 
            # Structure: Documents/HASH/Audio/...
            user_hash = "common"
            if "Documents" in parts:
                idx = parts.index("Documents")
                if len(parts) > idx + 2:
                    user_hash = parts[idx+1]
            
            file_hash = file_id
            shard = file_hash[:2]
            source_file = backup_path / shard / file_hash
            
            target_audio_dir = output_dir / user_hash / "Audio"
            target_audio_dir.mkdir(parents=True, exist_ok=True)
            
            dest_file = target_audio_dir / p.name
            
            if source_file.exists():
                shutil.copy2(source_file, dest_file)

    conn.close()
    print("-" * 30)
    print(f"Extraction finished. Data is in: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup_path", type=Path, help="Explicit path to iTunes backup folder", default=None)
    parser.add_argument("--output_path", type=Path, help="Output directory", default=None)
    parser.add_argument("--extract_audio", action="store_true", help="Extract audio files")
    parser.add_argument("--list", action="store_true", help="List available backups")
    
    args = parser.parse_args()
    
    backups = list_backups()
    
    if args.list:
        print("Available Backups:")
        for b, date in backups:
            print(f"- {b} ({date})")
        exit(0)

    selected_backup = None
    if args.backup_path:
        selected_backup = args.backup_path
    elif backups:
        selected_backup, date = backups[0]
        print(f"Using newest backup: {date}")
    else:
        print("No iOS backups found.")
        exit(1)

    out_dir = args.output_path if args.output_path else Path(__file__).parent / "extracted_wechat_db"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    extract_from_backup(selected_backup, out_dir, args.extract_audio)
