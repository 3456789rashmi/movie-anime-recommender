"""Catalog search page."""

import streamlit as st

from db import get_all_genres, search_titles
from ui import current_user, render_empty, render_title_card, setup_page

setup_page("Search")


@st.cache_data(ttl=300)
def genres() -> list[str]:
    return get_all_genres()


@st.cache_data(ttl=60)
def run_search(query, media_type, selected_genres, years, min_rating, sort_by, page):
    return search_titles(
        query=query,
        media_type=None if media_type == "All" else media_type.lower(),
        genres=list(selected_genres) or None,
        year_range=years,
        min_rating=min_rating,
        sort_by=sort_by,
        page=page,
        page_size=12,
    )


st.title("Search the catalog")
query = st.text_input("Search titles, alternate titles, or synopsis")
filters = st.columns(4)
media_type = filters[0].selectbox("Media type", ["All", "Movie", "Anime"])
selected_genres = filters[1].multiselect("Genres", genres())
min_year, max_year = filters[2].slider("Year range", 1900, 2026, (1900, 2026))
min_rating = filters[3].slider("Minimum rating", 0.0, 10.0, 0.0, 0.5)
sort_by = st.selectbox("Sort by", ["rating", "popularity", "year", "votes", "title"])
page = st.number_input("Page", min_value=1, value=1, step=1)

with st.spinner("Searching MongoDB..."):
    result = run_search(
        query, media_type, tuple(selected_genres), (min_year, max_year),
        min_rating, sort_by, page,
    )
st.caption(f"{result['total']:,} matching titles")
if not result["results"]:
    render_empty("No titles matched these filters.")
else:
    username = current_user()
    for title in result["results"]:
        render_title_card(title, username=username, show_watchlist=bool(username))
