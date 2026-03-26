import streamlit as st
import google.generativeai as genai
import datetime
import requests
import base64
from streamlit_mic_recorder import mic_recorder

# --- 1. 基本設定 ---
st.set_page_config(page_title="AI議事録くん", layout="centered")
st.title("🎙️ AI議事録 & 要約アプリ")

# 設定の読み込み
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOLDER_ID = st.secrets["FOLDER_ID"]
    GAS_URL = st.secrets["GAS_URL"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error("Secretsの設定（APIキーなど）が正しくありません。")
    st.stop()

# --- 2. 使えるAIモデルを自動で探す関数 ---
def get_working_model():
    # 優先して使いたいモデル名の候補（2026年の最新状況に合わせます）
    candidates = ['gemini-3-flash', 'gemini-1.5-flash', 'gemini-pro']
    
    available_models = [m.name.replace('models/', '') for m in genai.list_models() 
                        if 'generateContent' in m.supported_generation_methods]
    
    # 候補の中から最初に見つかったものを使う
    for cand in candidates:
        if cand in available_models:
            return genai.GenerativeModel(cand)
    
    # 候補がなければ、見つかった最初のモデルを使う
    if available_models:
        return genai.GenerativeModel(available_models[0])
    return None

# --- 3. Googleドライブ保存関数 ---
def save_to_drive_via_gas(content, file_name, mime_type):
    b64_data = base64.b64encode(content).decode('utf-8')
    payload = {
        "folderId": FOLDER_ID,
        "fileName": file_name,
        "mimeType": mime_type,
        "base64": b64_data
    }
    try:
        response = requests.post(GAS_URL, json=payload, timeout=60)
        return response.json().get("id") if response.status_code == 200 else None
    except:
        return None

# --- 4. メイン画面 ---
st.write("録音終了後、Googleドライブへ保存し、AIが解析します。")

audio = mic_recorder(
    start_prompt="⏺️ 録音開始",
    stop_prompt="⏹️ 録音終了・自動解析",
    key='recorder'
)

if audio:
    st.audio(audio['bytes'])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ドライブへ保存
    with st.spinner("Googleドライブへ保存中..."):
        audio_id = save_to_drive_via_gas(audio['bytes'], f"audio_{timestamp}.mp3", "audio/mpeg")
    
    if audio_id:
        st.success("✅ 音声を自動保存しました！")
        
        # AI解析
        with st.spinner("AIが議事録を作成中..."):
            model = get_working_model()
            if model:
                try:
                    response = model.generate_content([
                        "10名程度の話者を分離して文字起こしし、要約と決定事項をまとめてください。",
                        {"mime_type": "audio/mpeg", "data": audio['bytes']}
                    ])
                    
                    st.markdown("### 📝 解析結果")
                    st.write(response.text)

                    # テキストも保存
                    save_to_drive_via_gas(response.text.encode('utf-8'), f"minutes_{timestamp}.txt", "text/plain")
                    st.success("✅ 議事録も保存完了！")
                except Exception as e:
                    st.error(f"解析エラー: {e}")
            else:
                st.error("利用可能なAIモデルが見つかりませんでした。")
    else:
        st.error("ドライブ保存に失敗しました。GASの設定（全員に公開）を確認してください。")

st.divider()
st.caption("2026 AI Minutes Assistant")
