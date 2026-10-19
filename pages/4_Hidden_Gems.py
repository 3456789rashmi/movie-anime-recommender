"""Hidden-gem discovery page."""

import streamlit as st

from db import hidden_gems
from ui import render_empty, render_title_card, setup_page

setup_page("Hidden Gems")

st.title("Hidden Gems")
columns = st.columns(3)
min_rating = columns[0].slider("Minimum rating", 7.5, 10.0, 7.5, 0.1)
vote_percentile = columns[1].slider("Maximum vote percentile", 5, 50, 25)
media = columns[2].selectbox("Media type", ["All", "Movie", "Anime"])
media_type = None if media == "All" else media.lower()
with st.spinner("Finding highly rated, less-known titles..."):
    results = hidden_gems(media_type, min_rating, vote_percentile)
if not results:
    render_empty("No hidden gems matched those thresholds.")
for title in results[:30]:
    render_title_card(title)
