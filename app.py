"""Home page for the unified movie and anime recommendation engine."""

import streamlit as st

from db import hidden_gems, home_stats
from ui import render_empty, render_title_card, setup_page

setup_page("Home")


@st.cache_data(ttl=300)
def cached_stats() -> dict:
    return home_stats()


@st.cache_data(ttl=300)
def cached_gems() -> list[dict]:
    return hidden_gems(min_rating=7.5, max_votes_percentile=25)[:5]


st.title("Unified Movie + Anime Recommendation Engine")
st.write(
    "Discover movies and anime together using MongoDB search, aggregation "
    "pipelines, mood tags, analytics, and personalized recommendations."
)

with st.spinner("Loading live catalog statistics..."):
    stats = cached_stats()
metrics = st.columns(4)
for column, label, value in zip(
    metrics,
    ["Total titles", "Movies", "Anime", "Genres"],
    [stats["total_titles"], stats["movies"], stats["anime"], stats["total_genres"]],
):
    column.metric(label, f"{value:,}")

st.header("Hidden gems")
with st.spinner("Finding hidden gems..."):
    gems = cached_gems()
if gems:
    for gem in gems:
        render_title_card(gem)
else:
    render_empty("No hidden gems are available yet. Load the catalog first.")