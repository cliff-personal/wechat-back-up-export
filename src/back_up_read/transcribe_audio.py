import json
import os
import whisper
import tqdm

AUDIO_DIR = "/Users/cliff/workspace/wechat-business/src/back_up_read/converted_audio_xiaoxuzi"
JSON_PATH = "/Users/cliff/workspace/wechat-business/src/back_up_read/parsed_messages.json"


def process_chat(chat_data, audio_dir, model=None):
    if not model:
        print("Loading Whisper model (small)...")
        model = whisper.load_model("small")
        
    count = 0
    audio_files = set(f for f in os.listdir(audio_dir) if f.endswith(".mp3"))
    
    print(f"Scanning {len(chat_data.get('messages', []))} messages for audio...")
    
    for msg in chat_data.get("messages", []):
        if msg.get("type") == 34 and not msg.get("transcription"):
            msg_id = msg.get("id")
            if msg_id:
                filename = f"{msg_id}.mp3"
                if filename in audio_files:
                    filepath = os.path.join(audio_dir, filename)
                    try:
                        # fp16=False solves "FP16 is not supported on CPU" warning on Mac/CPU
                        result = model.transcribe(filepath, fp16=False)
                        text = result["text"].strip()
                        
                        msg["transcription"] = text
                        msg["content"] = f"[Voice] {text}"
                        count += 1
                    except Exception as e:
                        print(f"Error transcribing {filename}: {e}")
    return count

def main():
    print("Loading Whisper model (small)...")
    model = whisper.load_model("small")
    
    print(f"Loading messages from {JSON_PATH}...")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        # Assuming JSON_PATH is the old huge file or a list of chats
        # For compatibility with split files, this script might need adjustment
        # But for now let's keep it working for the list format
        messages = json.load(f)
        
    count = 0
    if not os.path.exists(AUDIO_DIR):
        print(f"Audio directory not found: {AUDIO_DIR}")
        return

    # Bulk process
    for conv in tqdm.tqdm(messages):
        count += process_chat(conv, AUDIO_DIR, model)
    
    print(f"Successfully transcribed {count} messages.")
    
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)
    print("Saved updated JSON.")

if __name__ == "__main__":
    main()
