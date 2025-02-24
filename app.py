import streamlit as st
import google.generativeai as genai
import os
import json
import requests
from dotenv import load_dotenv
from google.cloud import firestore
from datetime import datetime

# Load API keys
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Configure Gemini AI
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Firestore Setup (Ensure credentials are configured properly)
db = firestore.Client()

# Function: Fetch YouTube Video Recommendations
def recommend_youtube_videos(topic):
    """Fetches top YouTube videos related to the given topic."""
    try:
        search_url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": topic,
            "key": YOUTUBE_API_KEY,
            "maxResults": 3,
            "type": "video",
            "order": "viewCount",
            "videoEmbeddable": "true",
        }
        
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "items" not in data or not data["items"]:
            return ["⚠️ No videos found. Try a different topic."]
        
        videos = []
        for video in data["items"]:
            video_id = video["id"].get("videoId")
            if video_id:
                title = video["snippet"]["title"]
                thumbnail = video["snippet"]["thumbnails"]["medium"]["url"]
                videos.append({"title": title, "url": f"https://www.youtube.com/watch?v={video_id}", "thumbnail": thumbnail})
        
        return videos

    except requests.exceptions.RequestException as e:
        st.error(f"YouTube API Error: {e}")
        return [{"title": "⚠️ YouTube API Error", "url": "#", "thumbnail": ""}]

# Function: AI Learning Coach
def ai_learning_coach(student_name, query):
    """AI assistant that helps students with learning queries."""
    student_ref = db.collection("students").document(student_name)
    student_data = student_ref.get().to_dict() if student_ref.get().exists else {}

    # Fetch progress & history
    progress = student_data.get("progress", {})
    conversation_history = student_data.get("history", [])

    # Determine if a quiz is needed
    needs_quiz = any(keyword in query.lower() for keyword in ["i don't understand", "explain", "help me with"])

    prompt = f"""
    You are an AI Learning Coach for online education.
    Help students by answering their questions, explaining concepts, and guiding them.
    
    Student: {student_name}
    Progress: {json.dumps(progress)}
    
    User Query: {query}

    Guidelines:
    - If explaining, give a clear, direct answer.
    - If the student struggles, generate a **short quiz** (max 3 questions).
    - If relevant, recommend YouTube videos.
    """

    response = model.generate_content(prompt)
    ai_reply = response.text

    # Store conversation history
    conversation_history.append({"user": query, "assistant": ai_reply})
    student_ref.set({"history": conversation_history}, merge=True)

    return ai_reply, needs_quiz

# Streamlit UI
st.title("📚 AI Learning Coach with Gemini Pro")

# Student Name Input
student_name = st.text_input("Enter your name:", "")

if student_name:
    st.write(f"👋 Hello, {student_name}! What would you like to learn today?")

    # User Query Input
    user_query = st.text_area("Ask your Learning Coach:")

    if st.button("Get Help"):
        if user_query:
            response, needs_quiz = ai_learning_coach(student_name, user_query)
            st.write("🤖 **AI Learning Coach:**")
            st.markdown(response)

            # Recommend YouTube Videos if struggling
            if needs_quiz:
                topic = user_query  # Assume topic is derived from query
                video_recommendations = recommend_youtube_videos(topic)

                if video_recommendations:
                    st.write("📺 **Recommended YouTube Videos:**")
                    for video in video_recommendations:
                        st.markdown(f"[![{video['title']}]({video['thumbnail']})]({video['url']})", unsafe_allow_html=True)

        else:
            st.warning("Please enter a question.")

# Show Learning Progress
if student_name:
    st.subheader("📊 Your Learning Progress")
    student_ref = db.collection("students").document(student_name)
    student_data = student_ref.get().to_dict()

    if student_data:
        st.json(student_data.get("progress", {}))
    else:
        st.write("No progress tracked yet.")

    # Allow updating progress
    if st.button("Update Progress"):
        student_ref.set({"progress": {"last_updated": datetime.utcnow().isoformat()}}, merge=True)
        st.success("Progress updated!")