import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import dataclasses

@dataclasses.dataclass
class ChatMessage:
    id: str
    sender: str
    content: str
    timestamp: datetime
    is_sender: bool
    msg_type: str

def parse_wechat_exporter_json(json_path: Path) -> List[ChatMessage]:
    """
    Parse JSON output from WechatExporter.
    """
    if not json_path.exists():
        print(f"File not found: {json_path}")
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = []
    # Structure depends on the exporter settings, assuming specific structure
    # Adjust loop based on actual JSON format
    # Typically: { "conversations": [ { "messages": [ ... ] } ] }
    
    # Generic traverser if structure varies
    chat_list = data if isinstance(data, list) else data.get('conversations', [])
    
    for chat in chat_list:
        msgs = chat.get('messages', [])
        for m in msgs:
            # Normalize timestamp
            ts_str = m.get('timestamp') or m.get('createTime')
            try:
                ts = datetime.fromtimestamp(int(ts_str)) if str(ts_str).isdigit() else datetime.now()
            except:
                ts = datetime.now()

            msg = ChatMessage(
                id=str(m.get('id', '')),
                sender=m.get('sender', 'Unknown'),
                content=m.get('content', '') or m.get('text', ''),
                timestamp=ts,
                is_sender=m.get('isSender', False),
                msg_type=m.get('type', 'text')
            )
            messages.append(msg)
            
    print(f"Parsed {len(messages)} JSON messages.")
    return messages

def parse_wechat_csv(csv_path: Path) -> List[ChatMessage]:
    """
    Parse CSV export.
    Assumed columns: CreateTime, Sender, Type, Content, IsSender
    """
    messages = []
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return []
        
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Handle timestamp
                ts_str = row.get('CreateTime', '')
                try:
                     # Attempt generic parsing or timestamp
                    ts = datetime.fromisoformat(ts_str) if 'T' in ts_str else datetime.now()
                except:
                    ts = datetime.now()

                msg = ChatMessage(
                    id=f"csv-{len(messages)}",
                    sender=row.get('Sender', ''),
                    content=row.get('Content', ''),
                    timestamp=ts,
                    is_sender=row.get('IsSender', '0') == '1',
                    msg_type=row.get('Type', 'text')
                )
                messages.append(msg)
            except Exception as e:
                print(f"Skipping row error: {e}")

    print(f"Parsed {len(messages)} CSV messages.")
    return messages

if __name__ == "__main__":
    # Example usage
    base_dir = Path(__file__).parent
    
    # Look for exported files in 'output' folder
    output_dir = base_dir / "output" # User puts WechatExporter data here
    
    json_files = list(output_dir.glob("*.json"))
    csv_files = list(output_dir.glob("*.csv"))
    
    all_messages = []
    
    for f in json_files:
        print(f"Processing JSON: {f.name}")
        all_messages.extend(parse_wechat_exporter_json(f))
        
    for f in csv_files:
        print(f"Processing CSV: {f.name}")
        all_messages.extend(parse_wechat_csv(f))

    if all_messages:
        print(f"\nTotal messages loaded: {len(all_messages)}")
        print("Sample (first 3):")
        for m in all_messages[:3]:
            print(m)
    else:
        print("No messages parsed. Please convert your backup (using WechatExporter) and place .json/.csv files in the 'output' folder.")
