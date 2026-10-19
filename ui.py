"""Shared Streamlit presentation helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_title_card(
    title: dict[str, Any],
    *,
    username: str | None = None,
    show_watchlist: bool = False,
) -> None:
    """Render one title consistently across search and recommendation pages."""
    with st.container(border=True):
        columns = st.columns([1, 3])
        poster = title.get("poster_url")
        if poster:
            columns[0].image(poster, use_container_width=True)
        else:
            columns[0].markdown("🎬")
        with columns[1]:
            st.subheader(title.get("title", "Untitled"))
            details = " • ".join(
                str(value) for value in [title.get("year"), title.get("media_type")]
                if value
            )
            st.caption(details)
            st.write(
                f"⭐ {title.get('rating', 'N/A')}  |  "
                f"Genres: {', '.join(title.get('genres', [])) or 'Unknown'}"
            )
            synopsis = title.get("synopsis") or "No synopsis available."
            st.write(f"{synopsis[:220]}{'...' if len(synopsis) > 220 else ''}")
            if title.get("similarity_score") is not None:
                st.caption(f"Similarity score: {title['similarity_score']:.3f}")
            if title.get("reason"):
                st.caption(title["reason"])
            if show_watchlist and username:
                from db import add_to_watchlist

                if st.button("Add to watchlist", key=f"watch-{title.get('source_id')}"):
                    title_id = f"{title['media_type']}:{title['source_id']}"
                    try:
                        add_to_watchlist(username, title_id)
                        st.success("Added to your watchlist.")
                    except Exception as exc:
                        st.error(f"Could not update watchlist: {exc}")


def setup_page(title: str) -> None:
    """Apply the shared page title and sidebar branding."""
    st.set_page_config(page_title=title, page_icon="🎬", layout="wide")
    st.sidebar.title("Movie + Anime Recommender")
    st.sidebar.caption("MongoDB-powered recommendations")


def current_user() -> str | None:
    """Return the active username stored in Streamlit session state."""
    return st.session_state.get("username")


def render_empty(message: str) -> None:
    """Show a consistent empty-state message."""
    st.info(message)
