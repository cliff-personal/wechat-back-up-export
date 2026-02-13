import os
import subprocess
import concurrent.futures
from pathlib import Path
import shutil

# Paths
current_dir = Path(__file__).parent
DECODER_DIR = current_dir / "silk-v3-decoder"
CONVERTER_SCRIPT = DECODER_DIR / "converter.sh"

def check_dependencies():
    """Check if ffmpeg and decoder are available."""
    has_ffmpeg = shutil.which("ffmpeg") is not None
    # We allow the script to pass if converter exists.
    # On some systems, the user might need to chmod +x it.
    has_decoder = CONVERTER_SCRIPT.exists()
    
    if not has_ffmpeg:
        return False, "FFmpeg 未安装。请运行 `brew install ffmpeg`。"
    if not has_decoder:
        return False, f"找不到解码器脚本: {CONVERTER_SCRIPT}。请确认已克隆仓库并编译。"
        
    return True, "Ready"

def convert_one(file_path):
    """
    Convert a single .aud/.silk file to .mp3 using the converter.sh script.
    Usage: sh converter.sh <input_file> <output_format>
    The script creates <input_file>.mp3 in the same directory.
    """
    try:
        # converter.sh usage: sh converter.sh [input_file] [output_format]
        # output_format defaults to mp3
        # Ensure absolute path for script
        cmd = ["sh", str(CONVERTER_SCRIPT.resolve()), str(file_path), "mp3"]
        
        # Suppress output for clean logs
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if result.returncode == 0:
            return True
        return False
    except Exception:
        return False

def batch_convert(audio_dir, progress_callback=None):
    """
    Batch convert all .aud/.silk files in a directory to .mp3.
    """
    is_ready, msg = check_dependencies()
    if not is_ready:
        print(msg)
        return 0
        
    # Identify files
    files_to_convert = []
    
    try:
        if not os.path.exists(audio_dir):
            return 0
            
        for f in os.listdir(audio_dir):
            if f.endswith('.aud') or f.endswith('.silk'):
                # Check if mp3 already exists (filename + .mp3)
                # converter.sh usually outputs:  input.aud -> input.mp3 (replacing ext? or appending?)
                # Actually converter.sh behavior:
                # if input is "file.aud", output is "file.mp3"
                # Let's verify standard behavior.
                # Usually: $1.mp3
                
                # Check for likely output names
                target_mp3 = os.path.splitext(os.path.join(audio_dir, f))[0] + ".mp3"
                
                # If target mp3 doesn't exist, add to queue
                if not os.path.exists(target_mp3):
                   files_to_convert.append(os.path.join(audio_dir, f))
    except Exception as e:
        print(f"Error scanning dir: {e}")
        return 0

    total = len(files_to_convert)
    if total == 0:
        return 0
    
    converted_count = 0
    
    # Run in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(convert_one, f): f for f in files_to_convert}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if future.result():
                converted_count += 1
            
            if progress_callback:
                progress_callback(i + 1, total)
                
    return converted_count
