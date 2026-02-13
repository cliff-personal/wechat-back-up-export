import sqlite3
import hashlib
import json
from pathlib import Path
from datetime import datetime

# Path to the extracted DB directory
DB_DIR = Path(__file__).parent / "extracted_wechat_db"
OUTPUT_FILE = Path(__file__).parent / "parsed_messages.json"

def get_md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def extract_str(blob):
    if not blob: return ""
    try:
        # Try raw utf-8 first
        text = blob.decode('utf-8', errors='ignore')
        # Remove control chars (often caused by varints)
        # Keep alphanumeric, punctuation, CJK chars
        # Simple heuristic: remove unprintable ASCII control chars
        clean = "".join([c for c in text if c.isprintable() or c in '\n\r\t'])
        return clean.strip()
    except:
        return ""

def load_friends_map_from_wcdb():
    """
    Load UsrName -> NickName map from WCDB_Contact.sqlite
    """
    wcdb_files = list(DB_DIR.glob("*WCDB_Contact.sqlite"))
    if not wcdb_files:
        print("WCDB_Contact.sqlite not found.")
        return {}
    
    wcdb = wcdb_files[0]
    print(f"Loading contacts from {wcdb.name}...")
    
    try:
        conn = sqlite3.connect(wcdb)
        cursor = conn.cursor()
        # Friend table in WCDB_Contact usually has userName and dbContactRemark/dbContactProfile as BLOBs
        # We need to extract strings from these BLOBs (Protobuf fields)
        cursor.execute("SELECT userName, dbContactRemark, dbContactProfile, dbContactHeadImage FROM Friend")
        
        friends = {}
        count = 0
        for row in cursor.fetchall():
            usr = row[0]
            remark_blob = row[1]
            profile_blob = row[2]
            
            # Helper to extract clean string from protobuf blob
            def extract_str(blob):
                if not blob: return ""
                try:
                    # Try raw utf-8 first
                    text = blob.decode('utf-8', errors='ignore')
                    # Remove control chars (often caused by varints)
                    # Keep alphanumeric, punctuation, CJK chars
                    # Simple heuristic: remove unprintable ASCII control chars
                    clean = "".join([c for c in text if c.isprintable()])
                    return clean.strip()
                except:
                    return ""

            name = extract_str(remark_blob)
            if not name:
                name = extract_str(profile_blob)
            
            # If still no name, use ID
            if not name:
                name = usr
                
            friends[usr] = name
            count += 1
            
        print(f"  Loaded {count} contacts from WCDB.")
        conn.close()
        return friends
    except Exception as e:
        print(f"Error reading WCDB: {e}")
        return {}


def load_friends_map():
    """
    Load UsrName -> NickName map. Prioritizes WCDB_Contact, falls back to MM.sqlite.
    """
    # Try WCDB first (Richer data usually)
    friends = load_friends_map_from_wcdb()
    if friends:
        return friends

    # Fallback to MM.sqlite
    # Find MM.sqlite (might have hash in filename)
    mm_files = list(DB_DIR.glob("*MM.sqlite"))
    if not mm_files:
        print("MM.sqlite not found.")
        return {}
    
    mm_db = mm_files[0]
    print(f"Loading contacts from {mm_db.name}...")
    
    conn = sqlite3.connect(mm_db)
    cursor = conn.cursor()
    
    friends = {}
    try:
        cursor.execute("SELECT UsrName, NickName, RemarkName FROM Friend")  # Check if RemarkName exists in this version
        # If RemarkName fails, try just UsrName, NickName
    except sqlite3.OperationalError:
         # Fallback schema
        try:
             cursor.execute("SELECT UsrName, NickName FROM Friend")
        except Exception as e:
            print(f"Error reading Friend table: {e}")
            return {}

    for row in cursor.fetchall():
        usr = row[0]
        nick = row[1]
        remark = row[2] if len(row) > 2 else None
        
        display = remark if remark else nick
        if not display:
            display = usr
            
        friends[usr] = display
        
    conn.close()
    return friends

def parse_messages(friends_map, output_dir=None):
    if output_dir is None:
        output_dir = OUTPUT_FILE.parent / "parsed_data"

    all_conversations = []
    
    # 1. Map MD5(UsrName) -> NickName for easier lookup
    hash_map = {}
    for usr, nick in friends_map.items():
        h = get_md5(usr)
        hash_map[h] = (usr, nick)
        
    # 2. Iterate all message_*.sqlite files (use rglob for recursion)
    msg_dbs = list(DB_DIR.rglob("*message_*.sqlite"))
    
    if not msg_dbs:
        print("No message_*.sqlite files found.")
        return

    print(f"Found {len(msg_dbs)} message databases.")
    
    total_msgs = 0
    
    for db_path in msg_dbs:
        print(f"Reading {db_path.name}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables (Exclude ChatExt tables which are auxiliary)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Chat_%' AND name NOT LIKE 'ChatExt%'")
        tables = [r[0] for r in cursor.fetchall()]
        
        for table_name in tables:
            # Extract hash from table name (Chat_HASH)
            chat_hash = table_name.replace("Chat_", "")
            
            # Lookup friend
            friend_info = hash_map.get(chat_hash)
            if friend_info:
                usr, nick = friend_info
            else:
                usr, nick = ("Unknown", f"Unknown ({chat_hash})")
            
            # Read messages
            try:
                # Type 1=Text, 3=Image, 34=Voice, 47=Emoji, 49=AppMsg
                # Added MesLocalID for linking media files
                cursor.execute(f"SELECT CreateTime, Message, Des, Type, MesLocalID FROM {table_name} ORDER BY CreateTime ASC")
                rows = cursor.fetchall()
                
                msgs = []
                for r in rows:
                    ts = r[0]
                    content = r[1]
                    des = r[2] # 0=Recv, 1=Sent
                    msg_type = r[3]
                    msg_id = r[4]
                    
                    # Clean content to ensure valid JSON
                    if content is None:
                        content = ""
                    elif isinstance(content, bytes):
                        content = "[BINARY DATA]" # Or try decode?
                    else:
                        content = str(content).replace('\x00', '')

                    msgs.append({
                        "id": msg_id,
                        "timestamp": datetime.fromtimestamp(ts).isoformat(),
                        "sender": "Me" if des == 1 else nick,
                        "content": content,
                        "type": msg_type,
                        "is_sender": des == 1
                    })
                if msgs:
                    all_conversations.append({
                        "friend_id": usr,
                        "friend_name": nick,
                        "messages": msgs
                    })
                    total_msgs += len(msgs)
                    # print(f"  Parsed {len(msgs)} messages with {nick}")
                    
            except Exception as e:
                print(f"  Error reading table {table_name}: {e}")
                
        conn.close()

    data_dir = output_dir / "chats"
    data_dir.mkdir(exist_ok=True, parents=True)
    
    index_data = []

    for conv in all_conversations:
        friend_id = conv["friend_id"]
        friend_name = conv["friend_name"]
        
        # Sanitize filename
        safe_id = get_md5(friend_id)
        
        chat_file = data_dir / f"{safe_id}.json"
        
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(conv, f, ensure_ascii=False, indent=2)
            
        index_data.append({
            "friend_id": friend_id,
            "friend_name": friend_name,
            "message_count": len(conv["messages"]),
            "file_uuid": safe_id
        })
        
    # Save main index
    with open(output_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nDone! Parsed {total_msgs} messages from {len(all_conversations)} chats.")
    print(f"Saved index to: {output_dir / 'index.json'}")
    print(f"Saved {len(all_conversations)} chat files to: {data_dir}")

def load_friends_map_v2():
    # 1. Try WCDB_Contact (often best source for iOS)
    # Use rglob to find files in subdirectories (e.g. user hash folder)
    wcdb_files = list(DB_DIR.rglob("*WCDB_Contact.sqlite"))
    friends = {}
    
    if wcdb_files:
        print(f"Loading contacts from {wcdb_files[0].name}...")
        try:
            conn = sqlite3.connect(wcdb_files[0])
            cursor = conn.cursor()
            cursor.execute("SELECT userName, dbContactRemark FROM Friend")
            
            for row in cursor.fetchall():
                usr = row[0]
                blob = row[1]
                if not usr: continue
                
                name = ""
                if blob:
                    try:
                        # Dirty protobuf string extraction
                        raw = blob.decode('utf-8', errors='ignore')
                        # Remove control chars (often caused by varints)
                        # Keep alphanumeric, punctuation, CJK chars
                        # Heuristic: Find longest printable substring? Or just filter.
                        # Filter ASCII control codes (0-31) except 9,10,13
                        chars = [c for c in raw if ord(c) >= 32 or ord(c) in (9,10,13) or ord(c) > 127]
                        name = "".join(chars).strip()
                    except:
                        pass
                
                if name:
                    friends[usr] = name
            
            conn.close()
            print(f"  Loaded {len(friends)} names from WCDB.")
        except Exception as e:
            print(f"  Error reading WCDB: {e}")

    # 2. Merge/Fallback to MM.sqlite (old method)
    mm_files = list(DB_DIR.rglob("*MM.sqlite"))
    if mm_files:
        print(f"Loading contacts from {mm_files[0].name}...")
        try:
            conn = sqlite3.connect(mm_files[0])
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT UsrName, NickName, RemarkName FROM Friend")
                for row in cursor.fetchall():
                    usr = row[0]
                    nick = row[1]
                    remark = row[2] if len(row) > 2 else ""
                    
                    display = remark if remark else nick
                    if display:
                        # Prefer existing WCDB name if present? Actually let's trust MM.sqlite text fields more if they exist
                        # But typically MM.sqlite is empty on newer iOS versions?
                        if usr not in friends: 
                             friends[usr] = display
            except:
                pass 
            conn.close()
        except Exception as e:
             print(f"  Error reading MM.sqlite: {e}")
             
    return friends

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", type=Path, help="Input directory containing SQLite files", default=DB_DIR)
    parser.add_argument("--output", "-o", type=Path, help="Output directory for JSONs", default=Path(__file__).parent / "parsed_data")
    
    args = parser.parse_args()
    
    DB_DIR = args.input
    OUTPUT_FILE = args.output / "dummy.json" # Legacy variable name but used as base
    
    if not DB_DIR.exists():
        print(f"Input directory not found: {DB_DIR}")
        exit(1)
        
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    friends = load_friends_map_v2()
    print(f"Loaded {len(friends)} friends total.")
    parse_messages(friends, OUTPUT_FILE.parent)
