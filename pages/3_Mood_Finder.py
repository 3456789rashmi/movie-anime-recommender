"""Mood-based recommendation page."""

import streamlit as st

from db import mood_recommendations
from ui import render_empty, render_title_card, setup_page

setup_page("Mood Finder")


@st.cache_data(ttl=120)
def mood_results(mood: str, media_type: str | None) -> list[dict]:
    return mood_recommendations(mood, media_type=media_type, min_votes=10, limit=12)


st.title("Mood Finder")
moods = ["feel-good", "dark-thrilling", "mind-bending", "epic", "emotional"]
selected_mood = st.radio("Choose a mood", moods, horizontal=True)
media = st.radio("Media type", ["All", "Movies", "Anime"], horizontal=True)
media_type = {"All": None, "Movies": "movie", "Anime": "anime"}[media]
with st.spinner("Finding mood matches..."):
    results = mood_results(selected_mood, media_type)
if not results:
    render_empty("No titles have this mood tag yet.")
for title in results:
    render_title_card(title)
