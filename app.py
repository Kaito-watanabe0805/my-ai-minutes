import streamlit as st
import google.generativeai as genai
import datetime
import requests
import base64
from streamlit_mic_recorder import mic_recorder

st.set_page_config(page_title="AI議事録くん", layout="centered")
st.title("🎙️ AI議事録 & 要約アプリ")

# 設定読み込み
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
FOLDER_ID = st.secrets["FOLDER_ID"]
GAS_URL = st.secrets["GAS_URL"]

# Geminiの初期化（モデル名をより正確な形式に修正）
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def save_to_drive_via_gas(content, file_name, mime_type):
    b64_data = base64.b64encode(content).decode('utf-8')
    payload = {
        "folderId": FOLDER_ID,
        "fileName": file_name,
        "mimeType": mime_type,
        "base64": b64_data
    }
    try:
        response = requests.post(GAS_URL, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json().get("id")
        else:
            st.error(f"保存失敗（ステータスコード: {response.status_code}）")
            st.write("設定を確認してください。")
            return None
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

# --- メイン画面 ---
st.write("録音終了後、Googleドライブへ自動保存し、AIが解析します。")

audio = mic_recorder(
    start_prompt="⏺️ 録音開始",
    stop_prompt="⏹️ 録音終了・自動保存",
    key='recorder'
)

if audio:
    st.audio(audio['bytes'])
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 保存実行
    with st.spinner("Googleドライブへ保存中..."):
        audio_id = save_to_drive_via_gas(audio['bytes'], f"audio_{timestamp}.mp3", "audio/mpeg")
    
    # 2. 保存に成功した場合のみ解析へ進む
    if audio_id:
        st.success(f"✅ 音声を自動保存しました！")
        
        with st.spinner("AIが議事録を作成中..."):
            try:
                response = model.generate_content([
                    "10名程度の話者を『話者1』『話者2』のように分離して文字起こしし、要約と決定事項、ネクストアクションを詳しくまとめてください。",
                    {"mime_type": "audio/mpeg", "data": audio['bytes']}
                ])
                
                result_text = response.text
                st.markdown("### 📝 解析結果")
                st.write(result_text)

                # 議事録テキストも自動保存
                save_to_drive_via_gas(result_text.encode('utf-8'), f"minutes_{timestamp}.txt", "text/plain")
                st.success("✅ 議事録テキストも自動保存完了！")
            except Exception as e:
                st.error(f"AI解析中にエラーが発生しました: {e}")
    else:
        st.warning("保存に失敗したため、解析を中断しました。GASの公開設定（全員）を再確認してください。")

st.divider()
st.caption("Produced by Gemini Helper")
