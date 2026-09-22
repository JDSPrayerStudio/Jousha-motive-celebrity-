import streamlit as st
import os
from director import create_motivation_reel

# 1. Page Configuration
st.set_page_config(page_title="Motivation Reels Studio", page_icon="⚡")

# 2. Hide Streamlit Hamburger Menu, Footer, and Header to lock down code access
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("⚡ Motivation Reels Studio")
st.write("Generate unique 9:16 motivational videos built to bypass Facebook unoriginal content filters.")

# Check API Keys
if not os.environ.get("GEMINI_API_KEY"):
    st.warning("⚠️ GEMINI_API_KEY is missing. Please add it to your Streamlit Secrets.")
if not os.environ.get("PEXELS_API_KEY"):
    st.warning("⚠️ PEXELS_API_KEY is missing. Please add it to your Streamlit Secrets.")

# Studio Controls Form
with st.form("reel_form"):
    st.subheader("1. Content Settings")
    
    topic_input = st.text_input(
        "Motivation Topic (Leave blank for random viral topic):", 
        placeholder="e.g., Focus, Success, Failure, Overcoming fear, Silent grinding..."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        duration_choice = st.selectbox(
            "Target Duration:",
            ["10s", "15s", "20s", "25s", "30s", "60s", "90s"],
            index=4 # Default to 30s
        )
    with col2:
        time_setting = st.selectbox(
            "Time Context Style:",
            ["Morning", "Afternoon", "Night", "None"],
            index=0
        )
        
    st.subheader("2. Audience & Timezone Settings")
    audience_tz = st.selectbox(
        "Target Audience Timezone:",
        ["Nigeria (WAT - Africa/Lagos)", "USA (EST - America/New_York)", "USA (PST - America/Los_Angeles)"]
    )
        
    submitted = st.form_submit_button("🚀 Manufacture Facebook Reel")

# Session state for output persistence
if "generated_video" not in st.session_state:
    st.session_state.generated_video = None
if "generated_script" not in st.session_state:
    st.session_state.generated_script = None

if submitted:
    if not os.environ.get("GEMINI_API_KEY") or not os.environ.get("PEXELS_API_KEY"):
        st.error("Please ensure both Gemini and Pexels API keys are configured in your Streamlit app settings.")
    else:
        with st.spinner("🔄 Fetching Pexels unique clips, writing custom script, and manufacturing video..."):
            try:
                video_path, script_output = create_motivation_reel(
                    topic=topic_input,
                    duration_str=duration_choice,
                    time_of_day=time_setting,
                    audience_tz_str=audience_tz
                )
                st.session_state.generated_video = video_path
                st.session_state.generated_script = script_output
                st.success("🎉 Reel manufactured successfully!")
            except Exception as e:
                st.error(f"Generation Error: {e}")

# Display results if available
if st.session_state.generated_video and os.path.exists(st.session_state.generated_video):
    st.subheader("🎬 Your 9:16 Facebook Reel Preview")
    st.video(st.session_state.generated_video)
    
    st.subheader("📜 Generated Script")
    st.text_area("Script used for voiceover:", st.session_state.generated_script, height=120)
    
    with open(st.session_state.generated_video, "rb") as file:
        st.download_button(
            label="⬇️ Download Reel (.mp4)",
            data=file,
            file_name="facebook_motivation_reel.mp4",
            mime="video/mp4"
        )
        
