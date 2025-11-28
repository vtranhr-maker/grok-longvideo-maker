import streamlit as st
import requests  # Dùng requests cho Grok API vì SDK chưa ổn định
from gtts import gTTS
import moviepy.editor as mp
from PIL import Image, ImageDraw, ImageFont
import io
import os
import tempfile
import base64

# Config - Lấy API key từ Streamlit secrets hoặc input
GROK_API_KEY = st.secrets.get("GROK_API_KEY", None)
if not GROK_API_KEY:
    GROK_API_KEY = st.sidebar.text_input("Nhập Grok API Key (từ https://x.ai/api):", type="password")

def generate_script_with_grok(topic, length="long"):
    """Dùng Grok generate script dài qua API."""
    if not GROK_API_KEY or GROK_API_KEY == "your_api_key_here":
        return "# Script mẫu\n[SEGMENT 1] Intro: Chào mừng đến với video về " + topic + "!\n[SEGMENT 2] Phần 1: Giải thích cơ bản...\n(Thêm key thật để generate thật!)"
    
    prompt = f"""
    Tạo script video dài {length} (khoảng 1000-2000 từ) về chủ đề: {topic}.
    Cấu trúc: 
    - Intro (hook 30s)
    - Body (chia 3-5 phần chính, chi tiết)
    - Outro (kêu gọi hành động)
    Format: Markdown với [SEGMENT 1], [SEGMENT 2],... để dễ chia video.
    Giọng văn: Thân thiện, hấp dẫn, như YouTuber. Ngôn ngữ: Tiếng Việt.
    """
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "grok-beta",  # Model hiện tại (cập nhật nếu có mới)
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
        "temperature": 0.7
    }
    response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        st.error(f"Lỗi API: {response.status_code} - {response.text}")
        return "# Lỗi generate script. Kiểm tra API key!"

def text_to_speech(text, lang="vi"):
    """Tạo audio từ text (Tiếng Việt)."""
    if not text.strip():
        return None
    tts = gTTS(text=text, lang=lang, slow=False)
    audio_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    tts.save(audio_path)
    return audio_path

def create_text_clip(text, duration=5, fontsize=50, color="white"):
    """Tạo clip text overlay trên background đen."""
    img = Image.new('RGB', (1920, 1080), color='black')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", fontsize)
    except:
        font = ImageFont.load_default()
    
    # Wrap text đơn giản
    max_width = 1800
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        test_line = current_line + word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] < max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())
    
    y = 400
    for line in lines[:10]:  # Giới hạn 10 dòng
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((50, y), line, fill=color, font=font)
        y += 60
    
    img_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    img.save(img_path)
    clip = mp.ImageClip(img_path).set_duration(duration).set_fps(24)
    return clip, img_path

def generate_video(script, output_path="output.mp4"):
    """Ghép video từ script (giới hạn 3 segments cho test nhanh)."""
    if "[SEGMENT" not in script:
        st.warning("Script không có segments, dùng full text.")
        segments = [script]
    else:
        segments = [seg.strip() for seg in script.split("[SEGMENT") if seg.strip()][:3]  # Lấy 3 segments đầu
    
    clips = []
    audio_clips = []
    
    for i, seg in enumerate(segments):
        if "]" in seg:
            text = seg.split("]")[1].strip()[:300]  # Giới hạn text cho audio
        else:
            text = seg[:300]
        
        audio_path = text_to_speech(text)
        if not audio_path:
            continue
        audio_clip = mp.AudioFileClip(audio_path)
        
        text_clip, img_path = create_text_clip(text, duration=audio_clip.duration)
        video_clip = text_clip.set_audio(audio_clip)
        clips.append(video_clip)
        audio_clips.append(audio_clip)
        
        # Cleanup ngay
        os.unlink(audio_path)
        os.unlink(img_path)
    
    if not clips:
        st.error("Không tạo được clips!")
        return None
    
    final_video = mp.concatenate_videoclips(clips, method="compose")
    full_audio = mp.concatenate_audioclips(audio_clips)
    final_video = final_video.set_audio(full_audio)
    
    final_video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', verbose=False, logger=None)
    final_video.close()
    full_audio.close()
    
    return output_path

# Streamlit UI
st.title("🚀 App Tạo Video Dài Với Grok AI")
st.write("Nhập chủ đề, Grok generate script, rồi tự động tạo video MP4! (Test với key thật để full power)")

topic = st.text_input("Chủ đề video (ví dụ: 'Hướng dẫn nấu phở bò'):", "Hướng dẫn học Python cơ bản")
length = st.selectbox("Độ dài script:", ["ngắn (5 phút)", "dài (10+ phút)"])

if st.button("Tạo Video!"):
    if not GROK_API_KEY or GROK_API_KEY == "":
        st.warning("Nhập API key trước nhé! Lấy tại https://x.ai/api")
    else:
        with st.spinner("Grok đang generate script..."):
            script = generate_script_with_grok(topic, length)
            st.subheader("Script được generate:")
            st.markdown(script)
        
        with st.spinner("Đang render video... (1-3 phút)"):
            video_path = generate_video(script)
            if video_path and os.path.exists(video_path):
                st.success("Video sẵn sàng!")
                st.video(video_path)
                
                # Download
                with open(video_path, "rb") as file:
                    btn = st.download_button(
                        label="Tải video MP4",
                        data=file.read(),
                        file_name="grok_video.mp4",
                        mime="video/mp4"
                    )
                os.unlink(video_path)  # Cleanup
            else:
                st.error("Lỗi render video. Kiểm tra text ngắn hơn hoặc server mạnh hơn!")

# Sidebar tips
st.sidebar.info("""
**Tips nâng cao:**
- Deploy: Push repo lên GitHub → Connect Streamlit Cloud (free).
- Background đẹp: Thay ImageClip bằng VideoFileClip từ stock video.
- Voice pro: Thay gTTS bằng ElevenLabs API.
- API key: Lưu ở https://share.streamlit.io/secrets cho deploy.
""")
