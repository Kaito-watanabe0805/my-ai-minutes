import streamlit as st
import google.generativeai as genai
import datetime
import requests
import base64
from streamlit_mic_recorder import mic_recorder

# --- 1. 基本設定 ---
st.set_page_config(page_title="AI議事録プロ+", layout="wide")
st.title("🎙️ AI議事録プロ+ (過去ログ機能付)")

# セッション状態の初期化
if "current_minutes" not in st.session_state:
    st.session_state.current_minutes = None

# 設定読み込み
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
FOLDER_ID = st.secrets["FOLDER_ID"]
GAS_URL = st.secrets["GAS_URL"]
genai.configure(api_key=GEMINI_API_KEY)

# --- 2. 関数エリア ---
def get_file_list():
    try:
        response = requests.get(f"{GAS_URL}?folderId={FOLDER_ID}", timeout=10)
        return response.json()
    except: return []

def get_file_content(file_id):
    payload = {"action": "get_content", "fileId": file_id}
    response = requests.post(GAS_URL, json=payload)
    return response.json().get("content")

def save_to_drive(content, file_name, mime_type):
    b64_data = base64.b64encode(content).decode('utf-8')
    payload = {"folderId": FOLDER_ID, "fileName": file_name, "mimeType": mime_type, "base64": b64_data}
    requests.post(GAS_URL, json=payload)

# --- 3. サイドバー（過去ログ一覧） ---
st.sidebar.title("📁 過去の議事録")
if st.sidebar.button("一覧を更新"):
    st.rerun()

files = get_file_list()
if files:
    for f in files:
        if st.sidebar.button(f['name'], key=f['id']):
            st.session_state.current_minutes = get_file_content(f['id'])
else:
    st.sidebar.write("過去の議事録はありません")

# --- 4. メインエリア（録音） ---
col1, col2 = st.columns([1, 1])
with col1:
    audio = mic_recorder(start_prompt="⏺️ 録音開始", stop_prompt="⏹️ 終了・解析", key='recorder')

if audio:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    with st.spinner("AI解析中..."):
        # 音声を保存（バックグラウンド）
        save_to_drive(audio['bytes'], f"audio_{timestamp}.mp3", "audio/mpeg")
        # AI解析
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([
            "話者1、話者2のように分離して詳細に文字起こしし、最後に要約を書いてください。",
            {"mime_type": "audio/mpeg", "data": audio['bytes']}
        ])
        st.session_state.current_minutes = response.text
        # テキスト保存
        save_to_drive(response.text.encode('utf-8'), f"minutes_{timestamp}.txt", "text/plain")

# --- 5. 表示とチャット機能 ---
if st.session_state.current_minutes:
    st.markdown("### 📝 表示中の議事録")
    st.info("右上のサイドバーから過去のデータも呼び出せます。")
    st.text_area("", st.session_state.current_minutes, height=400)

    st.markdown("### 💬 AIへの指示・質問")
    st.caption("「表形式にして」「敬語を直して」「決定事項を抜き出して」など自由に指示できます。")
    user_input = st.text_input("ここに指示を入力...")
    
    if user_input:
        with st.spinner("思考中..."):
            model = genai.GenerativeModel("gemini-1.5-flash")
            chat_res = model.generate_content(f"以下の内容について指示に応えてください。\n内容：{st.session_state.current_minutes}\n指示：{user_input}")
            st.success("AIの回答：")
            st.write(chat_res.text)

st.divider()
st.caption("AI Minutes Assistant v2.0")
