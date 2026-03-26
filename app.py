import streamlit as st
import google.generativeai as genai
import datetime
import requests
import base64
from streamlit_mic_recorder import mic_recorder

# --- 1. 基本設定 ---
st.set_page_config(page_title="AI議事録プロ+", layout="wide")
st.title("🎙️ AI議事録プロ+ (自動命名機能付)")

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
st.write("録音終了後、AIが内容を判断して最適なファイル名を付け、自動保存します。")
audio = mic_recorder(start_prompt="⏺️ 録音開始", stop_prompt="⏹️ 終了・自動解析", key='recorder')

if audio:
    with st.spinner("AIが内容を読み取ってタイトルを考えています..."):
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # A. 議事録の生成
        response = model.generate_content([
            "10名程度の話者を分離して詳細に文字起こしし、最後に要約とネクストアクションを書いてください。",
            {"mime_type": "audio/mpeg", "data": audio['bytes']}
        ])
        minutes_text = response.text
        st.session_state.current_minutes = minutes_text

        # B. 自動タイトルの生成（ここが新機能！）
        title_response = model.generate_content(f"以下の議事録の内容から、ファイル名にふさわしい簡潔なタイトル（15文字以内）を考えて、タイトルのみを出力してください。余計な説明や記号、拡張子は不要です。\n内容：{minutes_text}")
        # 変な記号が含まれないように掃除し、日付を添える
        clean_title = title_response.text.strip().replace("/", "-").replace(" ", "_")
        timestamp = datetime.datetime.now().strftime("%y%m%d")
        final_filename = f"{timestamp}_{clean_title}"

        # C. ドライブへ保存（決まったタイトルを使用）
        save_to_drive(audio['bytes'], f"{final_filename}.mp3", "audio/mpeg")
        save_to_drive(minutes_text.encode('utf-8'), f"{final_filename}.txt", "text/plain")
        
        st.success(f"✅ 「{final_filename}」として保存しました！")

# --- 5. 表示とチャット機能 ---
if st.session_state.current_minutes:
    st.markdown("---")
    st.markdown("### 📝 表示中の議事録")
    st.text_area("", st.session_state.current_minutes, height=400)

    st.markdown("### 💬 AIへの指示・質問")
    user_input = st.text_input("ここに指示を入力（例：この内容を箇条書きの表にして）")
    
    if user_input:
        with st.spinner("思考中..."):
            model = genai.GenerativeModel("gemini-1.5-flash")
            chat_res = model.generate_content(f"以下の内容について指示に応えてください。\n内容：{st.session_state.current_minutes}\n指示：{user_input}")
            st.info(chat_res.text)

st.divider()
st.caption("AI Minutes Assistant v2.1 (Auto-Naming Edition)")
