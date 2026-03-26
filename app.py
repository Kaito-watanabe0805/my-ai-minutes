import streamlit as st
import google.generativeai as genai
import datetime
import requests
import base64
from streamlit_mic_recorder import mic_recorder

# --- 1. 基本設定 ---
st.set_page_config(page_title="AI議事録プロ", layout="centered")
st.title("🎙️ AI議事録プロ + 質問チャット")

# メモリ（セッション状態）の初期化
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# 設定の読み込み
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOLDER_ID = st.secrets["FOLDER_ID"]
    GAS_URL = st.secrets["GAS_URL"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("Secretsの設定を確認してください。")
    st.stop()

# --- 2. 使えるAIモデルを自動で探す ---
def get_working_model():
    available_models = [m.name.replace('models/', '') for m in genai.list_models() 
                        if 'generateContent' in m.supported_generation_methods]
    for cand in ['gemini-3-flash', 'gemini-1.5-flash', 'gemini-pro']:
        if cand in available_models:
            return genai.GenerativeModel(cand)
    return None

# --- 3. Googleドライブ保存関数 ---
def save_to_drive_via_gas(content, file_name, mime_type):
    b64_data = base64.b64encode(content).decode('utf-8')
    payload = {"folderId": FOLDER_ID, "fileName": file_name, "mimeType": mime_type, "base64": b64_data}
    try:
        response = requests.post(GAS_URL, json=payload, timeout=60)
        return response.json().get("id") if response.status_code == 200 else None
    except:
        return None

# --- 4. 録音エリア ---
st.write("録音終了後、AIが解析します。解析後は自由に質問が可能です。")

audio = mic_recorder(
    start_prompt="⏺️ 録音開始",
    stop_prompt="⏹️ 録音終了・解析開始",
    key='recorder'
)

if audio:
    st.audio(audio['bytes'])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with st.spinner("保存と解析を行っています..."):
        # ドライブ保存
        audio_id = save_to_drive_via_gas(audio['bytes'], f"audio_{timestamp}.mp3", "audio/mpeg")
        
        if audio_id:
            # AI解析
            model = get_working_model()
            if model:
                response = model.generate_content([
                    "10名程度の話者を分離して文字起こしし、要約と決定事項をまとめてください。",
                    {"mime_type": "audio/mpeg", "data": audio['bytes']}
                ])
                # 解析結果をメモリに保存
                st.session_state.analysis_result = response.text
                # テキストも保存
                save_to_drive_via_gas(response.text.encode('utf-8'), f"minutes_{timestamp}.txt", "text/plain")
            else:
                st.error("AIモデルが見つかりません。")
        else:
            st.error("保存に失敗しました。")

# --- 5. 解析結果の表示と追加質問エリア ---
if st.session_state.analysis_result:
    st.markdown("---")
    st.markdown("### 📝 議事録・要約内容")
    st.write(st.session_state.analysis_result)

    st.markdown("---")
    st.markdown("### 💡 この会議についてAIに質問する")
    user_query = st.text_input("例：予算について話していた箇所を抜粋して / 田中さんの宿題は何？")

    if user_query:
        with st.spinner("回答を生成中..."):
            model = get_working_model()
            # 議事録の内容をふまえて回答させる
            chat_response = model.generate_content(f"""
            以下の議事録の内容に基づいて、質問に答えてください。
            
            【議事録】
            {st.session_state.analysis_result}
            
            【質問】
            {user_query}
            """)
            st.info(chat_response.text)

st.divider()
st.caption("2026 AI Minutes Assistant with Chat")
