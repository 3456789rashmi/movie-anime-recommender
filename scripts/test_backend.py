"""Exercise every public function in db.py against the local MongoDB."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from pprint import pprint

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import (  # noqa: E402
    add_to_watchlist,
    create_user,
    delete_user,
    get_all_genres,
    get_db,
    get_title,
    get_titles,
    get_user,
    avg_rating_by_year,
    genre_counts,
    hidden_gems,
    media_type_comparison,
    mood_recommendations,
    personalized_recommendations,
    rate_title,
    remove_from_watchlist,
    search_titles,
    rating_distribution,
    similar_titles,
    taste_profile,
    top_by_genre_per_year,
    top_directors,
    top_studios,
)


def print_pipeline_result(name: str, results: list[dict]) -> None:
    """Print a compact, Windows-console-safe aggregation result summary."""
    preview = [
        {
            key: str(item.get(key, "")).encode("ascii", "replace").decode()
            for key in ("title", "genre", "studio", "director", "year", "count")
            if key in item
        }
        for item in results[:2]
    ]
    print(f"\n{name}: {len(results)} result(s)")
    print(preview)


def main() -> None:
    """Run backend smoke tests and print each result."""
    print("Database:", get_db().name)
    print("Titles collection:", get_titles().name)

    search_result = search_titles("Avatar", media_type="movie", page_size=2)
    print("\nsearch_titles:")
    pprint(search_result)

    print("\nget_title:")
    pprint(get_title("movie", 19995))

    print("\nget_all_genres:")
    print(get_all_genres("anime")[:10])

    print_pipeline_result(
        "similar_titles",
        similar_titles("movie", 19995, limit=2, cross_media=False),
    )
    print_pipeline_result(
        "mood_recommendations",
        mood_recommendations("epic", media_type="movie", min_votes=10, limit=2),
    )
    print_pipeline_result("hidden_gems", hidden_gems(media_type="movie")[:2])
    print_pipeline_result(
        "top_by_genre_per_year",
        top_by_genre_per_year(genre="Action", media_type="movie", limit=1)[:2],
    )
    print_pipeline_result("genre_counts", genre_counts("movie")[:2])
    print_pipeline_result("avg_rating_by_year", avg_rating_by_year("movie")[:2])
    print_pipeline_result("rating_distribution", rating_distribution("anime", bucket_count=5))
    print_pipeline_result("top_studios", top_studios(2))
    print_pipeline_result("top_directors", top_directors(2))
    print("\nmedia_type_comparison:")
    print(media_type_comparison())

    print("\ntaste_profile:")
    profile = taste_profile("demo_movie_fan")
    print({
        "favorite_genres": profile["favorite_genres"][:2],
        "summary": profile["summary"],
        "preferred_media_type_split": profile["preferred_media_type_split"],
    })
    print("\npersonalized_recommendations:")
    recommendations = personalized_recommendations("demo_movie_fan", limit=2)
    print_pipeline_result("personalized_recommendations", recommendations)
    demo_user = get_user("demo_movie_fan")
    excluded_ids = set(demo_user["watchlist"])
    excluded_ids.update(rating["title_id"] for rating in demo_user["ratings"])
    assert all(
        f"{recommendation['media_type']}:{recommendation['source_id']}" not in excluded_ids
        for recommendation in recommendations
    )
    assert all(
        recommendation["reason"].startswith("because you liked ")
        for recommendation in recommendations
    )

    username = f"backend_test_{uuid.uuid4().hex[:8]}"
    title_id = "movie:19995"
    try:
        print("\ncreate_user:")
        pprint(create_user(username))
        print("\nget_user:")
        pprint(get_user(username))
        print("\nadd_to_watchlist:", add_to_watchlist(username, title_id))
        print("rate_title:", rate_title(username, title_id, 9.5))
        print("remove_from_watchlist:", remove_from_watchlist(username, title_id))
        print("\nupdated user:")
        pprint(get_user(username))
    finally:
        print("\ndelete_user:", delete_user(username))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: backend smoke test failed: {exc}", file=sys.stderr)
        raise
