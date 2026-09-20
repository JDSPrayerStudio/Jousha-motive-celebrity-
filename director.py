import os
import random
import requests
from google import genai
from gtts import gTTS
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, ColorClip

def get_pexels_videos(query, count=3):
    """Fetches vertical background videos using script-derived keywords."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY is missing.")
        return []
    
    headers = {
        "Authorization": api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Use script-derived keywords, fallback to topic or generic cinematic background
    search_term = query if query else "cinematic dark motivation"
    url = f"https://api.pexels.com/v1/videos/search?query={requests.utils.quote(search_term)}&orientation=portrait&per_page=15"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            videos = data.get("videos", [])
            if not videos:
                # Fallback broad search if specific script keywords yield nothing
                fallback_url = "https://api.pexels.com/v1/videos/search?query=cinematic%20nature&orientation=portrait&per_page=10"
                response = requests.get(fallback_url, headers=headers)
                if response.status_code == 200:
                    videos = response.json().get("videos", [])
            
            if videos:
                random.shuffle(videos)
                downloaded_paths = []
                
                for i, v in enumerate(videos):
                    if len(downloaded_paths) >= count:
                        break
                    video_files = v.get("video_files", [])
                    if video_files:
                        file_url = video_files[0]["link"]
                        vid_path = f"pexels_bg_{i}.mp4"
                        
                        v_data = requests.get(file_url, headers=headers, stream=True)
                        if v_data.status_code == 200:
                            with open(vid_path, "wb") as f:
                                for chunk in v_data.iter_content(chunk_size=1024):
                                    f.write(chunk)
                            if os.path.exists(vid_path) and os.path.getsize(vid_path) > 5000:
                                downloaded_paths.append(vid_path)
                return downloaded_paths
    except Exception as e:
        print(f"Pexels exception: {e}")
    return []

def generate_motivation_script(topic, duration_str, time_of_day):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment variables.")

    client = genai.Client(api_key=api_key)
    
    word_limits = {
        "10s": "15 to 20 words max",
        "15s": "25 to 35 words max",
        "20s": "45 to 55 words max",
        "25s": "55 to 65 words max",
        "30s": "70 to 85 words max",
        "60s": "130 to 150 words max",
        "90s": "200 to 220 words max"
    }
    target_words = word_limits.get(duration_str, "70 to 85 words max")
    
    time_instruction = ""
    if time_of_day == "Morning":
        import datetime
        now = datetime.datetime.now()
        day_name = now.strftime("%A")
        date_str = now.strftime("%B %d, %Y")
        time_instruction = f"Incorporate the current temporal setting naturally: Mention today is {day_name}, {date_str}, and it is morning."
    elif time_of_day == "Afternoon":
        time_instruction = "Incorporate an afternoon reflection context naturally into the script."
    elif time_of_day == "Night":
        time_instruction = "Incorporate a night or evening reflection context naturally into the script."
    else:
        time_instruction = "Do not mention any specific time, day, or date."

    random_tones = ["intense and commanding", "deeply philosophical", "high-energy and urgent", "calm, wise, and grounded", "raw and uncompromising"]
    chosen_tone = random.choice(random_tones)

    prompt = f"""
    You are an elite viral motivation speech writer. 
    Topic: '{topic if topic else "unyielding discipline, personal growth, and overcoming obstacles"}'
    Target Length: Exactly {target_words}.
    Tone style: {chosen_tone}. Ensure it feels completely fresh, unique, and non-repetitive.
    Time Context: {time_instruction}
    
    Rules:
    - Return ONLY the spoken text script. No markdown formatting, no quotation marks, no narrator labels.
    - Make every single word count to match the target duration precisely.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text.strip()

def create_motivation_reel(topic, duration_str, time_of_day, output_filename="motivation_reel.mp4"):
    # Step 1: Generate the unique script first
    script_text = generate_motivation_script(topic, duration_str, time_of_day)
    
    # Step 2: Extract core words directly from the generated script to drive Pexels video search
    words = [w.strip(".,!?-") for w in script_text.split() if len(w) > 4]
    script_query = " ".join(words[:3]) if words else (topic if topic else "dark cinematic")

    audio_path = "voiceover.mp3"
    tts = gTTS(text=script_text, lang='en', slow=False)
    tts.save(audio_path)
    
    audio_clip = AudioFileClip(audio_path)
    target_duration = audio_clip.duration

    # Step 3: Fetch matching videos using script keywords
    clip_paths = get_pexels_videos(script_query, count=3)
    
    processed_clips = []
    if clip_paths:
        sub_duration = max(2.0, target_duration / len(clip_paths))
        for path in clip_paths:
            if os.path.exists(path):
                try:
                    vc = VideoFileClip(path)
                    w, h = vc.size
                    target_w, target_h = 1080, 1920
                    scale = max(target_w / w, target_h / h)
                    vc_resized = vc.resize(scale)
                    vc_cropped = vc_resized.crop(
                        x_center=vc_resized.w / 2, 
                        y_center=vc_resized.h / 2, 
                        width=target_w, 
                        height=target_h
                    )
                    sub = vc_cropped.subclip(0, min(sub_duration, vc_cropped.duration))
                    processed_clips.append(sub)
                except Exception as e:
                    print(f"Error processing clip {path}: {e}")

    if not processed_clips:
        bg_color = (15, 15, 20)
        fallback_clip = ColorClip(size=(1080, 1920), color=bg_color).set_duration(target_duration)
        processed_clips = [fallback_clip]

    final_video_bg = concatenate_videoclips(processed_clips, method="compose")
    
    if final_video_bg.duration < target_duration:
        loops = int(target_duration / final_video_bg.duration) + 1
        final_video_bg = concatenate_videoclips([final_video_bg] * loops).subclip(0, target_duration)
    else:
        final_video_bg = final_video_bg.subclip(0, target_duration)

    final_video = final_video_bg.set_audio(audio_clip)

    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="libmp3lame",
        preset="medium"
    )
    
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    return output_filename, script_text
        
