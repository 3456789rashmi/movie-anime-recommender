"""User profile, ratings, and personalized recommendations page."""

import pandas as pd
import plotly.express as px
import streamlit as st

from db import (
    create_user, find_title_by_name, get_title, get_user, list_usernames,
    personalized_recommendations, rate_title, taste_profile,
)
from ui import current_user, render_empty, render_title_card, setup_page

setup_page("Profile")


@st.cache_data(ttl=60)
def profile(username: str) -> dict:
    return taste_profile(username)


@st.cache_data(ttl=60)
def recommendations(username: str) -> list[dict]:
    return personalized_recommendations(username, limit=12)


users = list_usernames()
selected = st.selectbox("Select user", ["Create new user"] + users)
if selected == "Create new user":
    new_username = st.text_input("Username")
    if st.button("Create user") and new_username:
        try:
            create_user(new_username)
            st.session_state["username"] = new_username
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
else:
    st.session_state["username"] = selected

username = current_user()
if username:
    user = get_user(username)
    profile_data = profile(username)
    st.title(f"{username}'s profile")
    summary = profile_data["summary"]
    metrics = st.columns(2)
    metrics[0].metric("Rated titles", summary.get("rated_title_count", 0))
    metrics[1].metric("Average rating given", f"{summary.get('average_rating_given') or 0:.1f}")
    genres = profile_data["favorite_genres"][:10]
    if genres:
        st.plotly_chart(
            px.bar(pd.DataFrame(genres), x="weighted_score", y="genre", orientation="h", title="Favorite genres"),
            use_container_width=True,
        )
    st.subheader("Watchlist")
    watchlist = [get_title(*item.split(":", 1)) for item in user.get("watchlist", [])]
    for title in [item for item in watchlist if item]:
        render_title_card(title)
    st.subheader("Rate a title")
    title_query = st.text_input("Exact title to rate")
    title_result = find_title_by_name(title_query)
    score = st.slider("Your rating", 0.0, 10.0, 8.0, 0.5)
    if st.button("Save rating") and title_result:
        rate_title(username, f"{title_result['media_type']}:{title_result['source_id']}", score)
        st.cache_data.clear()
        st.success("Rating saved.")
    st.subheader("Personalized recommendations")
    with st.spinner("Building your recommendations..."):
        results = recommendations(username)
    if not results:
        render_empty("Rate a few titles to unlock personalized recommendations.")
    for title in results:
        render_title_card(title)
