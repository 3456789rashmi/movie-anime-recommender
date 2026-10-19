"""Similar-title recommendation page."""

import streamlit as st

from db import search_titles, similar_titles
from ui import render_empty, render_title_card, setup_page

setup_page("Recommendations")


@st.cache_data(ttl=120)
def title_options(query: str) -> list[dict]:
    return search_titles(query=query, page_size=20)["results"]


@st.cache_data(ttl=120)
def similar(media_type: str, source_id: int, cross_media: bool) -> list[dict]:
    return similar_titles(media_type, source_id, limit=10, cross_media=cross_media)


st.title("Similar titles")
query = st.text_input("Find a title to use as your starting point", "Avatar")
options = title_options(query)
if not options:
    render_empty("Search for a title to get recommendations.")
else:
    labels = [f"{item['title']} ({item['media_type']})" for item in options]
    selected = st.selectbox("Choose a title", labels)
    source = options[labels.index(selected)]
    same_tab, cross_tab = st.tabs(["Same media", "Cross-media (movies <-> anime)"])
    for tab, cross_media in [(same_tab, False), (cross_tab, True)]:
        with tab:
            with st.spinner("Building MongoDB similarity pipeline..."):
                results = similar(source["media_type"], source["source_id"], cross_media)
            if not results:
                render_empty("No similar titles were found.")
            for title in results:
                render_title_card(title)
