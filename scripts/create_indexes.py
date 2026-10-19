"""Create the indexes used by the unified movie and anime queries."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import db  # noqa: E402


def create_indexes() -> None:
    """Create or update indexes for titles and users."""
    titles = db["titles"]
    users = db["users"]

    # Prevent the same source record from being loaded twice for one media type.
    titles.create_index(
        [("media_type", 1), ("source_id", 1)],
        name="uq_media_type_source_id",
        unique=True,
    )

    # Support title/alternate-title/synopsis search; use a separate override
    # field so the application's language field is treated as ordinary data.
    titles.create_index(
        [("title", "text"), ("alt_titles", "text"), ("synopsis", "text")],
        name="text_title_alt_titles_synopsis",
        weights={"title": 10, "alt_titles": 5, "synopsis": 1},
        default_language="english",
        language_override="text_language",
    )

    # Support filtering and recommendation matching by one or more genres.
    titles.create_index("genres", name="genres_multikey")

    # Support top-rated, high-vote browsing separately for movies and anime.
    titles.create_index(
        [("media_type", 1), ("rating", -1), ("votes", -1)],
        name="media_rating_votes_desc",
    )

    # Support filtering or aggregating titles by computed mood tags.
    titles.create_index("mood_tags", name="mood_tags_multikey")

    # Support release-year filters and year-based aggregation buckets.
    titles.create_index("year", name="year")

    # Ensure each application user has one unique username.
    users.create_index("username", name="uq_username", unique=True)

    print("Titles indexes:")
    for index in titles.list_indexes():
        print(index)
    print("\nUsers indexes:")
    for index in users.list_indexes():
        print(index)


if __name__ == "__main__":
    try:
        create_indexes()
    except Exception as exc:
        print(f"ERROR: index creation failed: {exc}", file=sys.stderr)
        raise
