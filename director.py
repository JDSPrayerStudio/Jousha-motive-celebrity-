import os
import random
import time
import json
import asyncio
import subprocess
import requests
import streamlit as str_lit
from datetime import datetime
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types

def get_secure_key(key_name):
    try:
        if str_lit.secrets and key_name in str_lit.secrets:
            return str_lit.secrets[key_name]
    except Exception:
        pass
    return os.environ.get(key_name)

PEXELS_KEY = get_secure_key("PEXELS_API_KEY")
GEMINI_KEY = get_secure_key("GEMINI_API_KEY")

COLOR_BASE = "white"
FONT_SIZE = 54  
OUTLINE_WIDTH = 7  
OUTLINE_COLOR = "black"

# Persistent local history file to permanently stop video repetition across runs
HISTORY_FILE = "used_pexels_ids.json"

def load_used_pexels_ids():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_used_pexels_id(vid_id):
    used = load_used_pexels_ids()
    if vid_id not in used:
        used.append(vid_id)
        # Keep history capped at last 300 clips to prevent infinite bloat
        if len(used) > 300:
            used = used[-300:]
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(used, f)
        except Exception:
            pass

def generate_dynamic_pexels_queries(script_lines, count=4):
    """Extracts hyper-specific visual queries from the script text 
    while blocking cheap elements and enforcing high-end aesthetic variety."""
    client = genai.Client(api_key=GEMINI_KEY)
    
    combined_text = " ".join(script_lines)
    prompt = (
        f"Based on these script lines: '{combined_text}', generate {count} completely unique, "
        "high-end visual search queries for Pexels stock video.\n"
        "RULES:\n"
        "1. Match the exact vibe of the text (e.g., grit/grind -> intense focus, night driving, heavy machinery, elite workspaces; luxury -> hypercars, gold close-ups, penthouse views).\n"
        "2. ABSOLUTELY NO ordinary crowds, public transit, cheap clothing, or generic city traffic.\n"
        "3. Output ONLY a valid JSON list of strings, e.g., [\"query1\", \"query2\", \"query3\", \"query4\"]"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        if response and response.text:
            queries = json.loads(response.text)
            if isinstance(queries, list):
                return queries[:count]
    except Exception as e:
        print(f"Dynamic query generation fallback: {e}")
        
    # Expanded, randomized fallback pools to prevent repetition on API failure
    fallback_pools = [
        [
            "cinematic dark moody supercar night driving",
            "intense focus close up eyes determined gritty",
            "heavy industry gold melting glowing fire sparks",
            "luxury penthouse night skyline cinematic drone shot"
        ],
        [
            "dark gym weightlifting heavy iron sweat cinematic",
            "coder hacker typing fast monitors dark room neon",
            "private jet luxury lifestyle high altitude clouds",
            "boxing training intense punching bag shadowboxing"
        ],
        [
            "wall street stock exchange trading floor hustle",
            "architect blueprint late night working coffee",
            "fast motorcycle night city tunnel blur motion",
            "dark moody storm clouds lightning cinematic slow motion"
        ]
    ]
    return random.choice(fallback_pools)

def get_pexels_videos(script_lines, count=4):
    """Fetches fresh videos using script keywords and forces unique IDs 
    so backgrounds never repeat across video generations."""
    if not PEXELS_KEY:
        return []
    
    headers = {
        "Authorization": PEXELS_KEY,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    dynamic_queries = generate_dynamic_pexels_queries(script_lines, count=count)
    downloaded_paths = []
    used_ids = load_used_pexels_ids()
    
    for q_idx, query in enumerate(dynamic_queries):
        # Increased pagination depth from 1-5 to 1-25 to dig deeper into Pexels catalogs
        page_num = random.randint(1, 25)
        url = f"https://api.pexels.com/v1/videos/search?query={requests.utils.quote(query)}&orientation=portrait&per_page=30&page={page_num}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                if videos:
                    # Filter out any video IDs that have already been logged as used
                    available_videos = [v for v in videos if v.get("id") not in used_ids]
                    if not available_videos:
                        available_videos = videos # Fallback if all page results were used
                    
                    random.shuffle(available_videos)
                    
                    for v in available_videos:
                        v_id = v.get("id")
                        video_files = v.get("video_files", [])
                        if video_files:
                            # Prefer HD portrait files
                            file_url = video_files[0]["link"]
                            vid_path = f"pexels_bg_{q_idx}_{random.randint(10000,99999)}.mp4"
                            
                            v_data = requests.get(file_url, stream=True)
                            if v_data.status_code == 200:
                                with open(vid_path, "wb") as f:
                                    for chunk in v_data.iter_content(chunk_size=1024):
                                        f.write(chunk)
                                if os.path.exists(vid_path) and os.path.getsize(vid_path) > 10000:
                                    downloaded_paths.append(vid_path)
                                    # Save to permanent history so it never gets reused
                                    save_used_pexels_id(v_id)
                                    break
        except Exception as e:
            print(f"Pexels exception on query {query}: {e}")
            
    return downloaded_paths

def generate_structured_script(topic, duration_str, time_of_day, audience_tz_str):
    if not GEMINI_KEY:
        raise ValueError("GEMINI_KEY is missing from Streamlit secrets.")

    client = genai.Client(api_key=GEMINI_KEY)
    
    word_limits = {
        "10s": "15 to 20 words total",
        "15s": "25 to 35 words total",
        "20s": "45 to 55 words total",
        "25s": "55 to 65 words total",
        "30s": "70 to 85 words total"
    }
    target_words = word_limits.get(duration_str, "45 to 55 words total")
    
    tz_mapping = {
        "USA (EST - America/New_York)": "America/New_York",
        "USA (PST - America/Los_Angeles)": "America/Los_Angeles",
        "Nigeria (WAT - Africa/Lagos)": "Africa/Lagos"
    }
    selected_tz_name = tz_mapping.get(audience_tz_str, "America/New_York")
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

    if topic and len(topic.strip()) > 0:
        topic_instruction = f"CORE SUBJECT: Focus the speech on: '{topic.strip()}'."
    else:
        rotation_themes = [
            "raw mindset, relentless grinding, and outworking everyone in the room",
            "taking massive risks when everyone else plays it safe",
            "turning failure and losses into absolute fuel for dominance",
            "hyper-focus, discipline, and execution over empty talk",
            "building an unshakeable empire from the ground up with zero excuses"
        ]
        chosen_theme = random.choice(rotation_themes)
        topic_instruction = f"CORE SUBJECT: Focus heavily on {chosen_theme}."

    unique_seed = random.randint(1000000, 9999999)
    
    prompt = (
        f"{topic_instruction}\n"
        f"Target Length: {target_words}.\n"
        f"{time_instruction}\n"
        f"Variation Seed: {unique_seed} (Ensure complete script uniqueness).\n\n"
        "Write a powerful, high-retention motivational speech structured into JSON.\n"
        "CRITICAL WRITING STYLE RULES:\n"
        "1. THE HOOK: The first sentence ('hook') must be an aggressive, jaw-dropping pattern-interrupt statement within the first 1 to 2 seconds that forces viewers to stop scrolling immediately.\n"
        "2. HUMAN TONE & SLANG: Write like a real, gritty human speaker talking straight to the camera. Use natural speech cadence, short pauses indicated by commas or ellipses, and occasional organic street-smart phrasing or slang where it fits naturally.\n"
        "3. 'speech_lines': Break down the rest of the speech into 3 to 5 raw, punchy statements."
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

async def generate_phrase_audio(text_content, filename, voice_profile):
    import edge_tts
    
    voice_mapping = {
        "Andrew (Deep Gritty US Male)": "en-US-AndrewNeural",
        "Aria (Confident Cinematic Female)": "en-US-AriaNeural",
        "Christopher (Authoritative US Male)": "en-US-ChristopherNeural",
        "Guy (Smooth Street Motivation Male)": "en-US-GuyNeural"
    }
    selected_voice_id = voice_mapping.get(voice_profile, "en-US-AndrewNeural")
    
    success = False
    for _ in range(3):
        try:
            comm = edge_tts.Communicate(text_content, selected_voice_id, rate="+2%", pitch="-1Hz")
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

def create_motivation_reel(topic, duration_str, time_of_day, audience_tz_str, voice_profile="Andrew (Deep Gritty US Male)", output_filename="motivation_reel.mp4"):
    script_data = generate_structured_script(topic, duration_str, time_of_day, audience_tz_str)
    
    hook_text = clean_text_formatting(script_data['hook'])
    speech_lines = [clean_text_formatting(line) for line in script_data['speech_lines']]
    all_phrases = [hook_text] + speech_lines
    
    full_script_text = " ".join(all_phrases)

    async def build_audio_tracks():
        for idx, text in enumerate(all_phrases):
            await generate_phrase_audio(text, f"phrase_audio_{idx}.mp3", voice_profile)

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

    clip_count = max(3, int(total_video_duration // 4) + 1)
    clip_paths = get_pexels_videos(all_phrases, count=clip_count)
    
    master_bg_processed = "master_bg_unique.mp4"
    
    filter_fx = (
        "scale=1300:2300:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "fps=30,"
        "eq=brightness=0.01:contrast=1.35:saturation=1.50"
    )

    if clip_paths:
        clip_target_dur = max(2.5, total_video_duration / len(clip_paths))
        processed_part_files = []
        for i, clip_src in enumerate(clip_paths):
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

    # Fixed syntax error in cleanup routine (changed invalid 'end:' to 'except Exception:')
    for idx in range(len(all_phrases)):
        for ext in [".mp3", ".txt"]:
            fpath = f"phrase_audio_{idx}{ext}" if ext == ".mp3" else f"phrase_text_{idx}{ext}"
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass
                    
    if os.path.exists("final_voice_track.mp3"):
        try:
            os.remove("final_voice_track.mp3")
        except Exception:
            pass

    return output_filename, full_script_text
        
