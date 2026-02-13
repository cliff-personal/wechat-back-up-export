import streamlit as st
import json
import os
import subprocess
import sys
from pathlib import Path
import shutil
import hashlib
import re

# Add current dir to sys.path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Imports from local modules
try:
    from transcribe_audio import process_chat
except ImportError:
    process_chat = None

try:
    from audio_converter import batch_convert, check_dependencies as check_converter
except ImportError:
    batch_convert = None
    check_converter = lambda: (False, "Module not found")

st.set_page_config(page_title="WeChat Data Pipeline", layout="wide", page_icon="🧩")

st.title("🧩 WeChat Backup Pipeline")

# Session State & Defaults
default_root = str(Path.home() / "Downloads")
# Unified Output Root: always ~/Downloads/wechat-back-up-export/
FIXED_EXPORT_ROOT = str(Path.home() / "Downloads" / "wechat-back-up-export")

if "backup_path" not in st.session_state:
    st.session_state["backup_path"] = ""

if "scan_root" not in st.session_state:
    st.session_state["scan_root"] = default_root

# Initialize output paths to fixed defaults
# Also migrate old defaults if present (to handle reload without clearing session)
old_default_extract = os.path.join(default_root, "extracted_wechat_db")
old_default_parse = os.path.join(default_root, "parsed_data")
new_default_extract = os.path.join(FIXED_EXPORT_ROOT, "extracted_wechat_db")
new_default_parse = os.path.join(FIXED_EXPORT_ROOT, "parsed_data")

if "extract_output" not in st.session_state or st.session_state["extract_output"] == old_default_extract:
    st.session_state["extract_output"] = new_default_extract

if "parse_output" not in st.session_state or st.session_state["parse_output"] == old_default_parse:
    st.session_state["parse_output"] = new_default_parse
    
# Tabs
tab1, tab2, tab3 = st.tabs(["1️⃣ 提取 (Extract)", "2️⃣ 解析 (Parse)", "3️⃣ 浏览与导出 (View & Export)"])

# --- TAB 1: EXTRACT ---
with tab1:
    st.header("Step 1: Extract from iTunes Backup")
    st.info("从 iOS 备份中提取微信数据库和多媒体文件。")
    
    # 1. Search Config
    # Using key="scan_root" binds this to session state for persistence and callback
    scan_root = st.text_input(
        "📁 备份搜索根目录 (Search Root)", 
        key="scan_root", 
        help="程序将在此目录下寻找 iOS 备份文件夹 (含 Manifest.db)。默认: ~/Downloads"
    )

    # Auto-detect backups
    def get_backups(user_root):
        roots = [
            Path.home() / "Library/Application Support/MobileSync/Backup"
        ]
        if user_root:
            roots.insert(0, Path(user_root))
            
        candidates = []
        for r in roots:
            if r.exists():
                try:
                    for d in r.iterdir():
                        if d.is_dir() and (d / "Manifest.db").exists():
                            try:
                                candidates.append(str(d))
                            except: pass
                except PermissionError:
                    st.warning(f"无法访问目录 (请授予 Full Disk Access): {r}")
                except Exception:
                    pass
        return candidates

    backups = get_backups(scan_root)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if backups:
            selected = st.selectbox("检测到的备份:", backups)
            st.session_state["backup_path"] = selected
        else:
            st.warning("未检测到默认路径下的备份，请手动输入。")
            
        custom_path = st.text_input("手动输入备份路径:", value=st.session_state["backup_path"])
        if custom_path:
            st.session_state["backup_path"] = custom_path
            
    with col2:
        st.write("输出目录:")
        st.text_input("Extract Output", key="extract_output", label_visibility="collapsed")
        # Clarified label: "Extract Audio Files (No Parsing/Transcription)"
        extract_audio_opt = st.checkbox("提取语音文件 (Extract Audio Files)", value=True, help="仅复制音频文件，不进行转录 (No Transcription). 耗时较长。")

    if st.button("🚀 开始提取 (Start Extraction)"):
        if not st.session_state["backup_path"]:
            st.error("请选择或输入备份路径。")
        else:
            cmd = [
                sys.executable, 
                str(current_dir / "extract_wechat.py"),
                "--backup_path", st.session_state["backup_path"],
                "--output_path", st.session_state["extract_output"]
            ]
            if extract_audio_opt:
                cmd.append("--extract_audio")
            
            with st.status("正在提取...", expanded=True) as status:
                st.write(f"运行命令: {' '.join(cmd)}")
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    st.text(result.stdout)
                    if result.returncode == 0:
                        status.update(label="提取成功!", state="complete", expanded=False)
                        st.success("提取完成！请前往 Step 2 解析数据。")
                    else:
                        status.update(label="提取失败", state="error")
                        st.error(result.stderr)
                except Exception as e:
                    st.error(f"执行出错: {e}")

# --- TAB 2: PARSE ---
with tab2:
    st.header("Step 2: Parse Database")
    st.info("将提取的 SQLite 数据库解析为 JSON 格式（自动拆分好友文件）。")
    
    input_dir = st.text_input("输入目录 (Extraction Output):", value=st.session_state["extract_output"])
    output_dir = st.text_input("输出目录 (Parse Output):", value=st.session_state["parse_output"])
    
    st.session_state["parse_output"] = output_dir # sync
    
    if st.button("🧩 开始解析 (Start Parsing)"):
        if not os.path.exists(input_dir):
            st.error(f"输入目录不存在: {input_dir}")
        else:
            cmd = [
                sys.executable,
                str(current_dir / "parse_db.py"),
                "--input", input_dir,
                "--output", output_dir
            ]
            
            with st.status("正在解析...", expanded=True) as status:
                st.write(f"读取: {input_dir}")
                st.write(f"写入: {output_dir}")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    # Streamlit subprocess output handling is synchronous here
                    st.text(result.stdout)
                    
                    if result.returncode == 0:
                        status.update(label="解析成功!", state="complete", expanded=False)
                        st.success("解析完成！已生成 index.json 和聊天记录文件。请前往 Step 3 浏览。")
                    else:
                        st.error(result.stderr)
                        status.update(label="解析失败", state="error")
                except Exception as e:
                    st.error(f"执行出错: {e}")

# --- TAB 3: VIEW & EXPORT ---
with tab3:
    st.header("Step 3: Browse & Export")
    
    parse_out = st.session_state["parse_output"]
    index_file = os.path.join(parse_out, "index.json")
    chats_dir = os.path.join(parse_out, "chats")
    
    if not os.path.exists(index_file):
        st.warning(f"未找到索引文件: {index_file}。请先完成 Step 2 解析。")
    else:
        # Load Index
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except Exception as e:
            st.error(f"读取索引失败: {e}")
            st.stop()
            
        # Search & Sort
        col_search, col_sort = st.columns([3, 1])
        with col_search:
            search = st.text_input("🔍 搜索好友 (昵称/ID):")
        with col_sort:
            sort_by = st.selectbox("排序:", ["消息数量 (多->少)", "消息数量 (少->多)"])
            
        # Filter & Sort Logic
        filtered = [f for f in index_data if search.lower() in f['friend_name'].lower() or search.lower() in f['friend_id'].lower()]
        
        reverse_sort = True if "多->" in sort_by else False
        filtered.sort(key=lambda x: x['message_count'], reverse=reverse_sort)
        
        # Selection
        options = {f"{item['friend_name']} ({item['message_count']} msgs)": item for item in filtered}
        
        if not options:
            st.info("没有找到匹配的好友。")
        else:
            selected_label = st.selectbox("选择好友:", list(options.keys()))
            selected_friend = options[selected_label]
            
            # Load Chat Content
            chat_path = os.path.join(chats_dir, f"{selected_friend['file_uuid']}.json")
            
            if not os.path.exists(chat_path):
                st.error(f"聊天文件丢失: {chat_path}")
            else:
                with open(chat_path, 'r', encoding='utf-8') as f:
                    chat_data = json.load(f)
                
                # Try to locate the real Audio directory (It is usually under the OwnerHash, not FriendHash)
                # extract_output / <OwnerHash> / Audio
                # We scan one level deep to find "Audio"
                audio_root = st.session_state["extract_output"]
                real_audio_src = None
                
                # Helper to find Audio in a given root
                def find_audio_subdir(root_path):
                    if not root_path or not os.path.exists(root_path):
                        return None
                    # Direct check (unlikely)
                    if os.path.exists(os.path.join(root_path, "Audio")):
                        return os.path.join(root_path, "Audio")
                    # Subdir check
                    try:
                        subdirs = [os.path.join(root_path, d) for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]
                        for d in subdirs:
                            audio_d = os.path.join(d, "Audio")
                            if os.path.exists(audio_d):
                                return audio_d
                    except: pass
                    return None

                # 1. Search in configured output (extract_output)
                real_audio_src = find_audio_subdir(audio_root)
                
                # 2. If not found, try the FIXED_EXPORT_ROOT default extraction path
                if not real_audio_src:
                    fixed_extract_path = os.path.join(FIXED_EXPORT_ROOT, "extracted_wechat_db")
                    if fixed_extract_path != audio_root:
                         real_audio_src = find_audio_subdir(fixed_extract_path)

                # 3. If still not found, try the old default download path (backward compatibility)
                if not real_audio_src:
                    old_extract_path = os.path.join(Path.home() / "Downloads", "extracted_wechat_db")
                    if old_extract_path != audio_root:
                        real_audio_src = find_audio_subdir(old_extract_path)
                
                # First check if it's where we looked before (unlikely but possible if strict mapping)
                # ... (This logic is now replaced by find_audio_subdir)

                
                st.divider()
                st.subheader(f"💬 {chat_data['friend_name']}")
                st.caption(f"ID: {chat_data['friend_id']} | File: {selected_friend['file_uuid']}.json")
                
                # --- ACTIONS ---
                col_act1, col_act2 = st.columns([1, 1])

                # Placeholders for dynamic content update
                export_container = col_act1.empty()
                transcribe_container = col_act2.empty()

                # 1. Transcribe Logic (Run first to update data state if clicked)
                with transcribe_container.container():
                     # Audio Source Check
                    audio_src = real_audio_src
                    mp3_count = 0
                    aud_count = 0
                    
                    if not audio_src or not os.path.exists(audio_src):
                        st.warning(
                            "⚠️ **未找到语音文件夹 (Audio Not Found)**\n\n"
                            "可能是因为在 **Step 1 提取** 时未勾选 **“提取语音文件 (Extract Audio Files)”**，或者该备份中确实没有语音文件。\n\n"
                            "若需语音功能，请返回 Step 1，勾选该选项并重新运行提取。"
                        )
                        with st.expander("查看详细搜索路径 (Debug Path)"):
                            st.text(f"已尝试搜索:\n1. {audio_root}\n2. {FIXED_EXPORT_ROOT}/extracted_wechat_db")
                    else:
                        # Scan this specific chat's messages to see which audio files actually belong to IT
                        # This avoids counting ALL audio files in the backup (which might be shared or belong to others if structure logic is ambiguous)
                        # But realistically, audio_src usually points to ONE user hash folder. 
                        # However, current logic points to the FIRST 'Audio' folder found scanning all user subfolders if direct match fails.
                        # This is a bit risky. Let's refine the counting to be "Relevant Audio detected in Audio Source".
                        
                        # Better approach: The current `audio_src` (real_audio_src) is a global folder found by scanning. 
                        # We should check if the files *referenced in this chat* exist there as aud/silk vs mp3.
                        
                        msgs_with_voice = [m for m in chat_data.get("messages", []) if m.get("type") == 34]
                        voice_ids = [str(m.get("id")) for m in msgs_with_voice]
                        
                        # Count how many of THESE specific voice messages are converted
                        chat_aud_count = 0
                        chat_mp3_count = 0
                        
                        # We scan the directory ONCE to build a set of available files
                        all_files = set(os.listdir(audio_src))
                        
                        for vid in voice_ids:
                            # Check for source file (.aud, .silk)
                            if f"{vid}.aud" in all_files or f"{vid}.silk" in all_files:
                                chat_aud_count += 1
                                # Check for converted file (.mp3, .wav)
                                if f"{vid}.mp3" in all_files or f"{vid}.wav" in all_files:
                                    chat_mp3_count += 1

                        # Show Conversion UI specific to THIS chat
                        if chat_aud_count > 0:
                            st.write(f"📊 当前对话语音: {chat_aud_count} 条 | {chat_mp3_count} 已转 MP3")
                            is_ready, msg = check_converter()
                            need_convert = chat_mp3_count < chat_aud_count
                            
                            if not is_ready:
                                st.error(f"转换器不可用: {msg}")
                            elif need_convert:
                                if st.button(f"🔄 转换缺失的 {chat_aud_count - chat_mp3_count} 个文件"):
                                    convert_bar = st.progress(0, text="Starting conversion...")
                                    
                                    # Passing specific filter to batch_convert would be ideal, 
                                    # but current `batch_convert` converts specific directory. 
                                    # We can assume converting the whole folder is fine (simpler), 
                                    # OR we modify batch_convert.
                                    # For now, let's keep converting the folder, but the UI prompt is accurate to the user's context.
                                    # "Converting..." ensures dependencies are met.
                                    
                                    def update_prog(done, total):
                                        convert_bar.progress(done / total, text=f"Converting... {done}/{total}")
                                    
                                    # NOTE: This still converts ALL files in that folder. 
                                    # Usually acceptable as we want to convert everything eventually.
                                    converted = batch_convert(audio_src, progress_callback=update_prog)
                                    convert_bar.empty()
                                    if converted > 0:
                                        st.success(f"转换完成！")
                                        st.rerun()
                            else:
                                st.caption("✅ 当前对话语音已全部就绪")
                        else:
                            st.caption("没有包含语音消息。")

                    # Transcribe Button
                    # Check transcription status
                    transcribed_count = len([m for m in msgs_with_voice if m.get("transcription") or "[Voice]" in m.get("content", "")])
                    is_all_transcribed = (transcribed_count == len(msgs_with_voice)) and (len(msgs_with_voice) > 0)
                    
                    if is_all_transcribed:
                        st.success(f"✅ 语音转录已完成 ({transcribed_count}/{len(msgs_with_voice)})")
                        st.button("🎙️ 转录语音消息 (Transcribe Audio)", disabled=True, key="transcribe_btn_disabled")
                    else:
                        if st.button("🎙️ 转录语音消息 (Transcribe Audio)", disabled=False, key="transcribe_btn_active"):
                            if not audio_src or not os.path.exists(audio_src):
                                 st.error("Audio folder not found.")
                            # Check logic updated to match chat-specific counts
                            elif chat_mp3_count == 0 and chat_aud_count > 0:
                                 st.warning("请先转换音频。")
                            elif not process_chat:
                                st.error("Modules missing.")
                            else:
                                with st.spinner("Loading Whisper & transcribing..."):
                                    try:
                                        if "whisper_model" not in st.session_state:
                                            import whisper
                                            st.session_state["whisper_model"] = whisper.load_model("base")
                                        
                                        model = st.session_state["whisper_model"]
                                        # Reload chat_data from disk to ensure freshness before processing
                                        # (Though usually it matches memory, safer to be sure)
                                        count = process_chat(chat_data, audio_src, model)
                                        
                                        if count > 0:
                                            # Save to disk
                                            with open(chat_path, 'w', encoding='utf-8') as f:
                                                json.dump(chat_data, f, ensure_ascii=False, indent=2)
                                            st.success(f"✅ 成功转录 {count} 条消息！")
                                            # Force reload is implicit as script reruns or continues
                                            st.rerun()
                                        else:
                                            st.info("没有新的语音消息需要转录。")
                                    except Exception as e:
                                        st.error(f"转录失败: {e}")

                # 2. Export Rendering (Uses latest chat_data state)
                with export_container.container():
                    include_voice = st.checkbox("导出包含语音消息 (Include Voice)", value=True, help="如果需要导出语音转成的【文字内容】，请务必先点击右侧的【转录语音消息】按钮。")
                    
                    # Prepare export payload based on current in-memory chat_data (which might have been updated above)
                    export_payload = chat_data
                    if not include_voice:
                        export_payload = chat_data.copy()
                        export_payload["messages"] = [m for m in chat_data["messages"] if m.get("type") != 34]
                    
                    # Sanitize filename to prevent macOS security warnings / "malware" false positives
                    raw_name = chat_data['friend_name']
                    # Keep only alphanumeric, Chinese characters, spaces, and explicit safe delimiters
                    # Remove chars that often trigger OS filters or look like system paths
                    safe_name = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', raw_name).strip()
                    # Collapse multiple spaces
                    safe_name = re.sub(r'\s+', ' ', safe_name)
                    # Truncate length
                    if len(safe_name) > 50:
                        safe_name = safe_name[:50]
                    # Fallback if empty
                    if not safe_name:
                        safe_name = "unknown_friend"
                    
                    final_filename = f"wechat_{safe_name}.json"
                    json_str = json.dumps(export_payload, ensure_ascii=False, indent=2)

                    # Split actions: Download via Browser vs Save directly to Disk (Bypass macOS Gatekeeper)
                    col_dl, col_save = st.columns([1, 1.5])
                    
                    with col_dl:
                        st.download_button(
                            label="📥 下载 (Download)",
                            data=json_str,
                            file_name=final_filename,
                            mime="application/json"
                        )
                    
                    with col_save:
                        if st.button("💾 直接保存到硬盘 (Save to Disk)"):
                            # Save to 'exports' folder directly to avoid browser quarantine
                            export_dir = Path(st.session_state["parse_output"]) / "exports"
                            export_dir.mkdir(parents=True, exist_ok=True)
                            
                            save_path = export_dir / final_filename
                            try:
                                with open(save_path, "w", encoding="utf-8") as f:
                                    f.write(json_str)
                                st.success(f"已保存! 正在打开文件夹...")
                                # Auto-reveal in Finder on macOS
                                if sys.platform == "darwin":
                                    subprocess.run(["open", "-R", str(save_path)])
                                elif sys.platform == "win32":
                                    os.startfile(str(save_path))
                            except Exception as e:
                                st.error(f"保存失败: {e}")
                
                # --- MESSAGE VIEWER ---
                msgs = chat_data.get("messages", [])
                st.markdown(f"**显示最近 50 条消息 (共 {len(msgs)} 条)**")
                
                # Container for chat messages with custom CSS
                st.markdown("""
                <style>
                    .chat-message {
                        padding: 10px;
                        border-radius: 10px;
                        margin-bottom: 10px;
                        max-width: 70%;
                        display: inline-block;
                        position: relative;
                        word-wrap: break-word;
                    }
                    .chat-container {
                        display: flex;
                        width: 100%;
                        margin-bottom: 5px;
                    }
                    .sender-right {
                        justify-content: flex-end;
                    }
                    .sender-left {
                        justify-content: flex-start;
                    }
                    .bubble-right {
                        background-color: #95ec69; /* WeChat Green */
                        color: black;
                        border-top-right-radius: 2px;
                    }
                    .bubble-left {
                        background-color: #ffffff;
                        color: black;
                        border: 1px solid #e0e0e0;
                        border-top-left-radius: 2px;
                    }
                    .meta-info {
                        font-size: 0.7em;
                        color: #b0b0b0;
                        margin-bottom: 2px;
                        text-align: right;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                for msg in msgs[-50:]:
                    is_me = msg["is_sender"]
                    sender = "我" if is_me else chat_data["friend_name"]
                    
                    # Layout classes
                    container_class = "sender-right" if is_me else "sender-left"
                    bubble_class = "bubble-right" if is_me else "bubble-left"
                    
                    content = msg['content']
                    
                    # Simple text processing for better display
                    # Replace newlines
                    content = content.replace("\n", "<br>")
                    
                    st.markdown(
                        f"""
                        <div class="chat-container {container_class}">
                            <div class="chat-message {bubble_class}">
                                <div style="font-size: 0.75em; color: #888; margin-bottom: 4px;">
                                    {msg['timestamp'][5:16]}
                                </div>
                                {content}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
