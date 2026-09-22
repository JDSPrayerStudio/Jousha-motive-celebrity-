import os
import random
import time
import json
import asyncio
import subprocess
import requests
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types
from history_manager import filter_unused_pexels_clips

# Safely fetch keys from Streamlit Cloud Secrets or Environment variables
def get_secure_key(key_name):
    try:
        if st.secrets and key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return os.environ.get(key_name)

PEXELS_KEY = get_secure_key("PEXELS_API_KEY")
GEMINI_KEY = get_secure_key("GEMINI_API_KEY")

# ==========================================
# STYLE SETTINGS (BOLD & SAFE MARGIN CAPTIONS)
# ==========================================
COLOR_BASE = "white"
FONT_SIZE = 54  
OUTLINE_WIDTH = 7  
OUTLINE_COLOR = "black"

def get_pexels_videos(topic, time_of_day, count=3):
    """Fetches unique vertical background videos matching roads, cars, walking, and topic without repeats."""
    if not PEXELS_KEY:
        return []
    
    headers = {
        "Authorization": PEXELS_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Diverse motivational cinematic query variations (cars, roads, walking, city night/morning vibes)
    query_pool = [
        f"cinematic car driving on highway road night city {topic}",
        f"person walking alone on city street dark moody motivation",
        f"drone view moving forward down a dark highway road",
        f"cinematic traffic lights motion blur fast pace life",
        f"determined person walking forward urban street cinematic"
    ]
    
    selected_query = random.choice(query_pool)
    url = f"https://api.pexels.com/v1/videos/search?query={requests.utils.quote(selected_query)}&orientation=portrait&per_page=15"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            videos = data.get("videos", [])
            if videos:
                # Filter out already used clips from hidden studio history
                available_videos = filter_unused_pexels_clips(videos)
                random.shuffle(available_videos)
                
                downloaded_paths = []
                for i, v in enumerate(available_videos):
                    if len(downloaded_paths) >= count:
                        break
                    video_files = v.get("video_files", [])
                    if video_files:
                        file_url = video_files[0]["link"]
                        vid_path = f"pexels_bg_{i}_{random.randint(1000,9999)}.mp4"
                        
                        v_data = requests.get(file_url, stream=True)
                        if v_data.status_code == 200:
                            with open(vid_path, "wb") as f:
                                for chunk in v_data.iter_content(chunk_size=1024):
                                    f.write(chunk)
                            if os.path.exists(vid_path) and os.path.getsize(vid_path) > 10000:
                                downloaded_paths.append(vid_path)
                return downloaded_paths
    except Exception as e:
        print(f"Pexels exception: {e}")
    return []

def generate_structured_script(topic, duration_str, time_of_day, audience_tz_str):
    if not GEMINI_KEY:
        raise ValueError("GEMINI_KEY is missing from Streamlit secrets.")

    client = genai.Client(api_key=GEMINI_KEY)
    
    word_limits = {
        "10s": "15 to 20 words total",
        "15s": "25 to 35 words total",
        "20s": "45 to 55 words total",
        "25s": "55 to 65 words total",
        "30s": "70 to 85 words total",
        "60s": "130 to 150 words total",
        "90s": "200 to 220 words total"
    }
    target_words = word_limits.get(duration_str, "70 to 85 words total")
    
    tz_mapping = {
        "Nigeria (WAT - Africa/Lagos)": "Africa/Lagos",
        "USA (EST - America/New_York)": "America/New_York",
        "USA (PST - America/Los_Angeles)": "America/Los_Angeles"
    }
    selected_tz_name = tz_mapping.get(audience_tz_str, "Africa/Lagos")
    audience_time = datetime.now(ZoneInfo(selected_tz_name))
    
    day_name = audience_time.strftime("%A")
    month_name = audience_time.strftime("%B")
    day_num = audience_time.strftime("%d")

    if time_of_day and time_of_day.lower() != "none":
        time_instruction = (
            f"TEMPORARY CONTEXT: Today is {day_name}, {month_name} {day_num}, and it is currently {time_of_day.lower()}. "
            "Weave this organically into the speech without naming any year number."
        )
    else:
        time_instruction = "Do NOT mention any time of day, days of the week, dates, or years."

    prompt = (
        f"Topic/Theme: '{topic if topic else "unyielding discipline, pushing through limits, and building an unstoppable life"}'. "
        f"Target Length: {target_words}. "
        f"{time_instruction} "
        "Write a powerful, highly gripping, cinematic motivational speech structured into JSON. "
        "CRITICAL RULES:\n"
        "1. NO TEMPLATE RESTRICTIONS: Do not use rigid formulaic openings. Create a completely fresh, hard-hitting, raw hook that instantly grabs attention and forces viewers to keep watching.\n"
        "2. 'hook': The opening sentence must be exceptionally striking and intense.\n"
        "3. 'speech_lines': Break down the rest of the speech into 3 to 6 powerful, punchy sentences that flow seamlessly."
    )

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "hook": {"type": "STRING"},
            "speech_lines": {
                "type": "ARRAY",
                "items": {"type": "STRING"}
            }
        },
        "required": ["hook", "speech_lines"]
    }

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema
                    )
                )
                if response and response.text:
                    return json.loads(response.text)
            except Exception as e:
                print(f"Model {model_name} attempt {attempt} failed: {e}")
                time.sleep(1)
                
    raise RuntimeError("Gemini models are experiencing high traffic. Please try again.")

def clean_text_formatting(text):
    import re
    text = re.sub(r'[\r\t]+', ' ', text)
    text = re.sub(r'[^\w\s.,!?;:\-\n\'\"]+', '', text)
    return text.strip()

def wrap_horizontal_safe(text, max_chars=22):
    words = text.split(' ')
    lines_out = []
    current_line = ""
    for word in words:
        if len(current_line + " " + word) <= max_chars:
            current_line = (current_line + " " + word).strip()
        else:
            if current_line:
                lines_out.append(current_line)
            current_line = word
    if current_line:
        lines_out.append(current_line)
    return "\n".join(lines_out)

def get_audio_duration(filepath):
    res = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filepath
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(res.stdout.strip()) if res.stdout.strip() else 2.0

async def generate_phrase_audio(text_content, filename):
    import edge_tts
    success = False
    for _ in range(3):
        try:
            # Distinct American male voice (AndrewNeural)
            comm = edge_tts.Communicate(text_content, "en-US-AndrewNeural", rate="+0%", pitch="-1Hz")
            await comm.save(filename)
            if os.path.exists(filename) and os.path.getsize(filename) > 50:
                success = True
                break
        except Exception:
            await asyncio.sleep(1)
    if not success:
        from gtts import gTTS
        tts = gTTS(text=text_content, lang='en', slow=False)
        tts.save(filename)

def create_motivation_reel(topic, duration_str, time_of_day, audience_tz_str, output_filename="motivation_reel.mp4"):
    script_data = generate_structured_script(topic, duration_str, time_of_day, audience_tz_str)
    
    hook_text = clean_text_formatting(script_data['hook'])
    speech_lines = [clean_text_formatting(line) for line in script_data['speech_lines']]
    all_phrases = [hook_text] + speech_lines
    
    full_script_text = " ".join(all_phrases)

    async def build_audio_tracks():
        for idx, text in enumerate(all_phrases):
            await generate_phrase_audio(text, f"phrase_audio_{idx}.mp3")

    asyncio.run(build_audio_tracks())

    timed_segments = []
    current_time = 0.0
    for idx, phrase in enumerate(all_phrases):
        audio_file = f"phrase_audio_{idx}.mp3"
        dur = get_audio_duration(audio_file)
        timed_segments.append({
            "phrase": phrase,
            "audio": audio_file,
            "start": current_time,
            "end": current_time + dur,
            "duration": dur
        })
        current_time += dur

    total_video_duration = current_time + 0.2

    audio_concat_txt = "audio_concat.txt"
    with open(audio_concat_txt, "w") as f_a:
        for seg in timed_segments:
            f_a.write(f"file '{seg['audio']}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", audio_concat_txt, "-c", "copy", "final_voice_track.mp3"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    clip_paths = get_pexels_videos(topic, time_of_day, count=3)
    
    master_bg_processed = "master_bg_unique.mp4"
    filter_fx = (
        "scale=1300:2300:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "fps=30,"
        "eq=brightness=0.02:contrast=1.14:saturation=1.18,"
        "vignette=PI/4"
    )

    if clip_paths:
        clip_target_dur = max(3.0, total_video_duration / len(clip_paths))
        processed_part_files = []
        for i, clip_src in enumerate(clip_paths[:3]):
            part_file = f"bg_part_{i}.mp4"
            processed_part_files.append(part_file)
            subprocess.run([
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", clip_src,
                "-t", str(clip_target_dur),
                "-vf", filter_fx,
                "-c:v", "libx264", "-preset", "fast", "-an", part_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        bg_concat_txt = "bg_concat.txt"
        with open(bg_concat_txt, "w") as f_b:
            for pf in processed_part_files:
                f_b.write(f"file '{pf}'\n")

        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", bg_concat_txt, "-c", "copy", master_bg_processed
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x14161E:s=1080x1920:d={total_video_duration}",
            "-vf", filter_fx, "-c:v", "libx264", "-t", str(total_video_duration), master_bg_processed
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "Sans"

    filter_parts = ["[0:v]copy[v0]"]
    total_segs = len(timed_segments)

    for idx, seg in enumerate(timed_segments):
        horizontal_block = wrap_horizontal_safe(seg["phrase"], max_chars=22)
        txt_filename = f"phrase_text_{idx}.txt"
        with open(txt_filename, "w", encoding="utf-8") as tf:
            tf.write(horizontal_block)
            
        in_stream = f"v{idx}"
        out_stream = "outv" if idx == total_segs - 1 else f"v{idx+1}"
        time_window = f"between(t,{seg['start']:.3f},{seg['end']:.3f})"
        
        fontfile_arg = f"fontfile='{font_path}':" if os.path.exists(font_path) else ""
        
        filter_expr = (
            f"[{in_stream}]drawtext="
            f"textfile='{txt_filename}':"
            f"fontcolor={COLOR_BASE}:"
            f"fontsize={FONT_SIZE}:"
            f"{fontfile_arg}"
            f"borderw={OUTLINE_WIDTH}:"
            f"bordercolor={OUTLINE_COLOR}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2 + 150:"
            f"shadowx=3:shadowy=3:"
            f"enable='{time_window}'[{out_stream}]"
        )
        filter_parts.append(filter_expr)

    filter_complex_string = ";\n".join(filter_parts)

    subprocess.run([
        "ffmpeg", "-y", "-i", master_bg_processed, "-i", "final_voice_track.mp3",
        "-filter_complex", filter_complex_string, "-map", "[outv]", "-map", "1:a",
        "-c:v", "libx264", "-r", "30", "-fps_mode", "cfr", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-shortest", output_filename
    ], check=True)

    for idx in range(len(all_phrases)):
        for ext in [".mp3", ".txt"]:
            fpath = f"phrase_audio_{idx}{ext}" if ext == ".mp3" else f"phrase_text_{idx}{ext}"
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except:
                    pass
    if os.path.exists("final_voice_track.mp3"):
        os.remove("final_voice_track.mp3")

    return output_filename, full_script_text
    
