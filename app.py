import streamlit as st
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import datetime
from streamlit_mic_recorder import mic_recorder

# --- 設定エリア ---
st.set_page_config(page_title="AI議事録くん", layout="centered")
st.title("🎙️ AI議事録 & 要約アプリ")

# 1. 鍵の読み込み（Streamlit Secretsを使用）
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GOOGLE_DRIVE_JSON = st.secrets["GOOGLE_DRIVE_JSON"]
FOLDER_ID = st.secrets["FOLDER_ID"]

genai.configure(api_key=GEMINI_API_KEY)

# 2. Googleドライブの準備
def upload_to_drive(content, file_name, mime_type='text/plain'):
    creds = service_account.Credentials.from_service_account_info(GOOGLE_DRIVE_JSON)
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {'name': file_name, 'parents': [FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 画面表示 ---
st.write("90分までの録音に対応。終了後、自動で要約します。")
st.info("💡 録音中、ブラウザの「スリープ防止」が機能しますが、念のため画面を閉じないでください。")

# 録音コンポーネント
audio = mic_recorder(
    start_prompt="⏺️ 録音開始",
    stop_prompt="⏹️ 録音終了・解析",
    key='recorder'
)

if audio:
    st.audio(audio['bytes'])
    st.success("録音完了！解析中...")

    # Googleドライブへ音声保存
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_filename = f"audio_{timestamp}.mp3"
    drive_id = upload_to_drive(audio['bytes'], audio_filename, 'audio/mpeg')
    st.write(f"✅ 音声保存完了 (ID: {drive_id})")

    # Geminiによる解析
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # 音声データをGeminiに送信
    with st.spinner("AIが10名の話者を分離して要約中...（数分かかる場合があります）"):
        response = model.generate_content([
            "この音声ファイルを文字起こししてください。10名程度の話者がいるので、話者1、話者2のように分離してください。その後、議事録、重要事項、ネクストアクションを詳しくまとめてください。",
            {"mime_type": "audio/mpeg", "data": audio['bytes']}
        ])
        
        result_text = response.text
        st.markdown("### 📝 解析結果")
        st.write(result_text)

        # テキスト結果もドライブに保存
        text_filename = f"minutes_{timestamp}.txt"
        upload_to_drive(result_text.encode('utf-8'), text_filename)
        st.success("✅ 議事録もドライブに保存しました！")

st.divider()
st.caption("Produced by Gemini Helper")
