import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent / "extracted_wechat_db"
CONTACT_DB = list(DB_DIR.glob("*WCDB_Contact.sqlite"))[0]

def decode_field(blob):
    if not blob:
        return ""
    try:
        # Try raw utf-8
        return blob.decode('utf-8')
    except:
        pass
    
    # Try finding the first readable string (simple heuristic)
    try:
        # Basic heuristic for protobuf strings: length prefixed or tag-length-value
        # For now, let's just sanitise the binary string to printable chars
        # This is "dirty" but often sufficient for extracting names without full proto definition
        text = blob.decode('utf-8', errors='ignore')
        # Filter for CJK and standard ASCII
        clean = "".join([c for c in text if c.isprintable()])
        return clean
    except:
        return "<binary>"

conn = sqlite3.connect(CONTACT_DB)
cursor = conn.cursor()

# Get columns to check
cursor.execute("SELECT userName, dbContactRemark, dbContactProfile, dbContactHeadImage FROM Friend LIMIT 10")
rows = cursor.fetchall()

print(f"{'UserName':<20} | {'Remark (Parsed)':<20} | {'Profile (Parsed)':<20}")
print("-" * 60)

for row in rows:
    usr = row[0]
    remark = decode_field(row[1])
    profile = decode_field(row[2])
    
    print(f"{usr:<20} | {remark:<20} | {profile:<20}")

conn.close()
