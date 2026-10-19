"""Shared Streamlit presentation helpers."""

from __future__ import annotations

from typing import Any

import streamlit as st


def apply_theme() -> None:
    """Apply shared visual styling across all Streamlit pages."""
    st.markdown(
        """
        <style>
        :root {
            --ink: #172033;
            --muted: #64748b;
            --brand: #0f766e;
            --brand-dark: #115e59;
            --surface: #ffffff;
            --background: #f4f7fb;
        }

        .stApp {
            background: var(--background);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #102a43 0%, #163b56 100%);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #f8fafc;
        }

        h1, h2, h3 {
            color: var(--ink);
            letter-spacing: -0.02em;
        }

        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 12px 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted);
        }

        [data-testid="stMetricValue"] {
            color: var(--brand-dark);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface);
            border-color: #dbe4ee;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }

        .stButton > button {
            border: 0;
            border-radius: 9px;
            background: var(--brand);
            color: white;
            font-weight: 700;
            transition: background 120ms ease, transform 120ms ease;
        }

        .stButton > button:hover {
            background: var(--brand-dark);
            color: white;
            transform: translateY(-1px);
        }

        .hero {
            background: linear-gradient(135deg, #0f766e 0%, #155e75 55%, #1e3a8a 100%);
            border-radius: 20px;
            color: white;
            padding: 30px 34px;
            margin: 0 0 26px;
            box-shadow: 0 12px 28px rgba(15, 118, 110, 0.2);
        }

        .hero h1 {
            color: white;
            font-size: 2.35rem;
            margin: 0 0 8px;
        }

        .hero p {
            color: #dff7f5;
            font-size: 1.05rem;
            margin: 0;
        }

        .section-kicker {
            color: var(--brand);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    apply_theme()
    st.sidebar.markdown("## 🎬 CineVerse")
    st.sidebar.caption("Movie + anime discovery")
    st.sidebar.markdown("---")
    st.sidebar.caption("Powered by MongoDB aggregation and personalized taste profiles.")


def current_user() -> str | None:
    """Return the active username stored in Streamlit session state."""
    return st.session_state.get("username")


def render_empty(message: str) -> None:
    """Show a consistent empty-state message."""
    st.info(message)
