import streamlit as st
import json
import pandas as pd
from pathlib import Path

# Config
current_dir = Path(__file__).parent
DATA_FILE = current_dir / "parsed_messages.json"

st.set_page_config(page_title="WeChat Backup Viewer", layout="wide")

@st.cache_data
def load_data():
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    st.title("📱 WeChat History Viewer")
    
    data = load_data()
    
    if not data:
        st.error(f"No data found in {DATA_FILE}. Please run parse_db.py first.")
        return

    # Sidebar: Friend Selector with Search
    st.sidebar.header("Friends List")
    
    # Sort friends by message count descending
    data.sort(key=lambda x: len(x['messages']), reverse=True)
    
    # --- PERFORMANCE FIX: Server-side Pagination ---
    # Don't send 40k options to the frontend selection box, it crashes websocket.
    
    filter_mode = st.sidebar.radio("Filter Mode", ["Top 50 Active", "Search All"], index=0)
    
    candidates_indices = []
    
    if filter_mode == "Top 50 Active":
        candidates_indices = list(range(min(len(data), 50)))
        st.sidebar.caption("Showing top 50 friends by message count.")
    else:
        name_query = st.sidebar.text_input("One-time Search", placeholder="Type name or ID...")
        if name_query:
            count = 0
            for i, chat in enumerate(data):
                if name_query.lower() in chat['friend_name'].lower() or \
                   name_query.lower() in chat['friend_id'].lower():
                    candidates_indices.append(i)
                    count += 1
                    if count >= 100: # Limit search results
                        break
            if not candidates_indices:
                st.sidebar.warning("No matches found.")
        else:
            st.sidebar.info("Type above to search 39k+ contacts")
            
    if not candidates_indices:
        # Fallback to display something if search empty but avoid crash
        candidates_indices = [0] if data else []

    # Create options mapping: "Name (Count)" -> Index
    friend_options = {
        f"{data[i]['friend_name']} ({len(data[i]['messages'])} msgs)": i 
        for i in candidates_indices
    }
    
    if not friend_options:
        st.stop()
    
    selected_label = st.sidebar.selectbox(
        "Select Result",
        options=list(friend_options.keys()),
        index=0
    )
    
    # Simple lookup
    selected_index = friend_options[selected_label]
    chat = data[selected_index]
    # -----------------------------------------------
    
    # Message Content Search (Search within the selected chat)
    st.sidebar.markdown("---")
    search_query = st.sidebar.text_input("Search in chat", placeholder="Filter messages...")
    
    # Main View
    st.header(f"Chat with: {chat['friend_name']}")
    st.caption(f"ID: {chat['friend_id']} | Total Messages: {len(chat['messages'])}")
    
    # Function to filter messages
    filtered_messages = chat['messages']
    
    # Filter by search string
    if search_query:
        filtered_messages = [
            m for m in filtered_messages 
            if search_query.lower() in str(m['content']).lower()
        ]
        st.info(f"Filtered: {len(filtered_messages)} messages found for '{search_query}'")

    # Export Options (Using filtered data)
    col1, col2 = st.columns(2)
    with col1:
        # JSON Export
        export_data = {**chat, "messages": filtered_messages}
        chat_json = json.dumps(export_data, ensure_ascii=False, indent=2)
        st.download_button(
            label="⬇️ Download JSON",
            data=chat_json,
            file_name=f"wechat_{chat['friend_name']}_filtered.json",
            mime="application/json"
        )
    with col2:
        # Text Export
        text_content = f"Chat History with {chat['friend_name']}\n"
        if search_query:
            text_content += f"Filter: {search_query}\n"
        text_content += "\n"
            
        for msg in filtered_messages:
            text_content += f"[{msg['timestamp']}] {msg['sender']}: {msg['content']}\n"
            
        st.download_button(
            label="⬇️ Download Text",
            data=text_content,
            file_name=f"wechat_{chat['friend_name']}_filtered.txt",
            mime="text/plain"
        )
        
    st.divider()

    # Chat Bubble Styles
    st.markdown("""
    <style>
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
    }
    .msg-row {
        display: flex;
        width: 100%;
    }
    .msg-row.sent {
        justify-content: flex-end;
    }
    .msg-row.received {
        justify-content: flex-start;
    }
    .bubble {
        max-width: 70%;
        padding: 10px 15px;
        border-radius: 15px;
        position: relative;
        font-family: sans-serif;
    }
    .sent .bubble {
        background-color: #95ec69; /* WeChat Green */
        color: black;
        border-bottom-right-radius: 5px;
    }
    .received .bubble {
        background-color: #ffffff;
        color: black;
        border: 1px solid #e0e0e0;
        border-bottom-left-radius: 5px;
    }
    .meta {
        font-size: 0.75em;
        color: #888;
        margin-top: 5px;
        display: block;
    }
    </style>
    """, unsafe_allow_html=True)

    # Rendering Messages
    
    # Display Limit
    DISPLAY_LIMIT = 500
    if len(filtered_messages) > DISPLAY_LIMIT and not search_query:
        st.warning(f"Showing last {DISPLAY_LIMIT} messages for performance. Use export to key full history or search to find older messages.")
        to_display = filtered_messages[-DISPLAY_LIMIT:]
    else:
        to_display = filtered_messages

    for msg in to_display:
        # Align: Sender (Me) -> Right, Receiver (Friend) -> Left
        row_class = "sent" if msg['is_sender'] else "received"
        sender_name = "Me" if msg['is_sender'] else msg['sender']
        
        # Handle different message types (basic text only currently supports full display)
        content_display = msg['content']
        if msg['type'] == 3:
            content_display = "🖼️ [Image]"
        elif msg['type'] == 34:
            content_display = "🔊 [Voice]"
        elif msg['type'] == 49:
            content_display = "🔗 [Link/AppMsg]"
        elif msg['type'] == 47:
            content_display = "😊 [Sticker]"
            
        st.markdown(f"""
        <div class="msg-row {row_class}">
            <div class="bubble">
                <div>{content_display}</div>
                <span class="meta">{msg['timestamp']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
