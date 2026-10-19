"""Catalog analytics page."""

import pandas as pd
import plotly.express as px
import streamlit as st

from db import (
    avg_rating_by_year, genre_counts, media_type_comparison,
    rating_distribution, top_directors, top_studios,
)
from ui import render_empty, setup_page

setup_page("Analytics")


@st.cache_data(ttl=300)
def analytics():
    return {
        "genres": genre_counts(),
        "years": avg_rating_by_year(),
        "ratings": rating_distribution(bucket_count=10),
        "studios": top_studios(10),
        "directors": top_directors(10),
        "comparison": media_type_comparison(),
    }


st.title("Catalog analytics")
with st.spinner("Running aggregation analytics..."):
    data = analytics()
if not data["genres"]:
    render_empty("Analytics are unavailable until titles are loaded.")
else:
    st.plotly_chart(
        px.bar(pd.DataFrame(data["genres"][:20]), x="genre", y="count", title="Genre counts"),
        use_container_width=True,
    )
    st.plotly_chart(
        px.line(pd.DataFrame(data["years"]), x="year", y="average_rating", title="Average rating by year"),
        use_container_width=True,
    )
    st.plotly_chart(
        px.bar(pd.DataFrame(data["ratings"]), x="rating_from", y="count", title="Rating distribution"),
        use_container_width=True,
    )
    columns = st.columns(2)
    columns[0].plotly_chart(
        px.bar(pd.DataFrame(data["studios"]), x="title_count", y="studio", orientation="h", title="Top anime studios"),
        use_container_width=True,
    )
    columns[1].plotly_chart(
        px.bar(pd.DataFrame(data["directors"]), x="title_count", y="director", orientation="h", title="Top movie directors"),
        use_container_width=True,
    )
    st.subheader("Movies vs anime")
    st.dataframe(pd.DataFrame(data["comparison"][0]["by_media_type"]), use_container_width=True)
