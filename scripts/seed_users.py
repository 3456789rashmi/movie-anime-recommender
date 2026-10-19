"""Seed repeatable demo users with ratings for personalization demos."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import create_user, db, rate_title  # noqa: E402


DEMO_USERS = {
    "demo_movie_fan": {
        "ratings": {
            "Avatar": 9.0,
            "The Dark Knight": 9.5,
            "Inception": 9.0,
            "The Lord of the Rings: The Fellowship of the Ring": 9.5,
        },
        "watchlist": ["Interstellar"],
    },
    "demo_anime_fan": {
        "ratings": {
            "Naruto": 8.5,
            "Spirited Away": 9.5,
            "Howl's Moving Castle": 9.0,
            "Death Note": 9.0,
        },
        "watchlist": ["One Piece"],
    },
    "demo_cross_media_fan": {
        "ratings": {
            "The Matrix": 9.0,
            "Inception": 9.5,
            "Fullmetal Alchemist: Brotherhood": 9.5,
            "Attack on Titan": 9.0,
        },
        "watchlist": ["Avatar"],
    },
}


def title_id_for(title: str) -> str | None:
    """Resolve a title name to the unified string ID."""
    document = db["titles"].find_one({"title": title}, {"_id": 1})
    if document is None:
        print(f"WARNING: title not found, skipping '{title}'")
        return None
    return str(document["_id"])


def seed_users() -> None:
    """Replace the demo users and populate their ratings/watchlists."""
    for username, preferences in DEMO_USERS.items():
        db["users"].delete_one({"username": username})
        create_user(username)
        for title, rating in preferences["ratings"].items():
            title_id = title_id_for(title)
            if title_id:
                rate_title(username, title_id, rating)
        for title in preferences["watchlist"]:
            title_id = title_id_for(title)
            if title_id:
                db["users"].update_one(
                    {"username": username},
                    {"$addToSet": {"watchlist": title_id}},
                )
        print(f"Seeded {username}")


if __name__ == "__main__":
    try:
        seed_users()
        print(f"Seeded {len(DEMO_USERS)} demo users.")
    except Exception as exc:
        print(f"ERROR: demo user seeding failed: {exc}", file=sys.stderr)
        raise
