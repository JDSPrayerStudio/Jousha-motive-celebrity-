import os
import json

HISTORY_FILE = "used_pexels_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"used_clips": []}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history_data, f)
    except Exception as e:
        print(f"Error saving history: {e}")

def filter_unused_pexels_clips(clips):
    """Filters out video IDs that have already been used in previous generations."""
    history = load_history()
    used_ids = set(history.get("used_clips", []))
    
    fresh_clips = []
    new_ids_to_track = []
    
    for clip in clips:
        vid_id = str(clip.get("id"))
        if vid_id not in used_ids:
            fresh_clips.append(clip)
            new_ids_to_track.append(vid_id)
            
    # If all fetched clips were used, fallback to the full list to prevent failing
    if not fresh_clips and clips:
        fresh_clips = clips
        for clip in clips:
            new_ids_to_track.append(str(clip.get("id")))

    # Save newly used IDs back to hidden storage (limit to last 200 IDs)
    updated_used = list(used_ids.union(new_ids_to_track))[-200:]
    save_history({"used_clips": updated_used})
    
    return fresh_clips
  
