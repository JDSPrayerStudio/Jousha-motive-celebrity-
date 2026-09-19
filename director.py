import os
import random
import requests
from google import genai
from gtts import gTTS
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, TextClip, CompositeVideoClip, colorx

def get_pexels_videos(query, count=4):
    """Fetches multiple unique vertical background videos from Pexels."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return []
    
    headers = {"Authorization": api_key}
    # Search for vertical videos (9:16)
    url = f"https://api.pexels.com/videos/search?query={query}&orientation=portrait&per_page=15"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            videos = data.get("videos", [])
            if videos:
                random.shuffle(videos)
                selected_clips = []
                downloaded_paths = []
                
                for v in videos:
                    if len(downloaded_paths) >= count:
                        break
                    # Find a suitable HD/SD video file link
                    video_files = v.get("video_files", [])
                    # Sort by width/height to get portrait HD
                    portrait_files = [f for f in video_files if f.get("width", 0) <= f.get("height", 0)]
                    if not portrait_files:
                        portrait_files = video_files
                    
                    if portrait_files:
                        file_url = portrait_files[0]["link"]
                        vid_path = f"pexels_bg_{len(downloaded_paths)}.mp4"
                        
                        # Download video file
                        v_data = requests.get(file_url, stream=True)
                        if v_data.status_code == 200:
                            with open(vid_path, "wb") as f:
                                for chunk in v_data.iter_content(chunk_size=1024):
                                    f.write(chunk)
                            downloaded_paths.append(vid_path)
                return downloaded_paths
    except Exception as e:
        print(f"Pexels fetch error: {e}")
    return []

def generate_motivation_script(topic, duration_str, time_of_day):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment variables.")

    client = genai.Client(api_key=api_key)
    
    # Target word counts for strict duration pacing (approx 140 words per minute)
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
    # 1. Generate Script via Gemini
    script_text = generate_motivation_script(topic, duration_str, time_of_day)
    
    # 2. Convert Script to Audio using gTTS
    audio_path = "voiceover.mp3"
    tts = gTTS(text=script_text, lang='en', slow=False)
    tts.save(audio_path)
    
    audio_clip = AudioFileClip(audio_path)
    target_duration = audio_clip.duration

    # 3. Fetch Background Video Clips from Pexels (3 to 5 unique clips)
    search_query = topic if topic else "cinematic dark motivation background"
    clip_paths = get_pexels_videos(search_query, count=4)
    
    if not clip_paths:
        raise RuntimeError("Failed to fetch background videos from Pexels. Check your PEXELS_API_KEY.")

    # 4. Process and concatenate video clips to match audio duration
    sub_duration = max(2.0, target_duration / len(clip_paths))
    processed_clips = []
    
    for path in clip_paths:
        if os.path.exists(path):
            try:
                vc = VideoFileClip(path)
                # Resize and crop to 9:16 vertical format (1080x1920)
                # First resize to height 1920 or width 1080 proportionally
                w, h = vc.size
                target_w, target_h = 1080, 1920
                
                # Resize clip so it covers 1080x1920
                scale = max(target_w / w, target_h / h)
                vc_resized = vc.resize(scale)
                
                # Crop center to 1080x1920
                vc_cropped = vc_resized.crop(
                    x_center=vc_resized.w / 2, 
                    y_center=vc_resized.h / 2, 
                    width=target_w, 
                    height=target_h
                )
                
                # Trim clip portion
                sub = vc_cropped.subclip(0, min(sub_duration, vc_cropped.duration))
                processed_clips.append(sub)
            except Exception as e:
                print(f"Error processing clip {path}: {e}")

    if not processed_clips:
        raise RuntimeError("Could not process background clips.")

    final_video_bg = concatenate_videoclips(processed_clips, method="compose")
    
    # If background video is shorter than audio, loop it or trim audio. Let's loop video or set duration.
    if final_video_bg.duration < target_duration:
        loops = int(target_duration / final_video_bg.duration) + 1
        final_video_bg = concatenate_videoclips([final_video_bg] * loops).subclip(0, target_duration)
    else:
        final_video_bg = final_video_bg.subclip(0, target_duration)

    # 5. Add Voiceover Audio to Video
    final_video = final_video_bg.set_audio(audio_clip)

    # 6. Export Final 9:16 Reel
    final_video.write_videofile(
        output_filename,
        fps=24,
        codec="libx264",
        audio_codec="libmp3lame",
        preset="medium"
    )
    
    # Clean up temporary audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    return output_filename, script_text
                      
