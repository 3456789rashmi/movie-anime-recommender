"""Clean the source CSV files and load a unified MongoDB titles collection."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path
from pprint import pprint
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import VALIDATOR, db  # noqa: E402


BATCH_SIZE = 1000
EXCLUDE_ADULT = True
MOOD_TAGS = {
    "feel-good": {"Comedy", "Family", "Slice of Life"},
    "dark-thrilling": {"Thriller", "Horror", "Crime", "Mystery"},
    "mind-bending": {"Sci-Fi", "Science Fiction", "Mystery", "Psychological"},
    "epic": {"Adventure", "Fantasy", "Action"},
    "emotional": {"Drama", "Romance"},
}


def is_missing(value: Any) -> bool:
    """Return whether a CSV value is missing or blank."""
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    return bool(missing) if isinstance(missing, bool) else False


def clean_text(value: Any) -> str | None:
    """Convert a CSV value to trimmed text, or None when it is missing."""
    if is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def parse_json_array(value: Any) -> list[Any]:
    """Safely parse a JSON/Python-list CSV value."""
    if is_missing(value):
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return []
    return parsed if isinstance(parsed, list) else []


def named_values(value: Any) -> list[str]:
    """Parse an array of objects and return unique non-empty names."""
    result: list[str] = []
    for item in parse_json_array(value):
        name = clean_text(item.get("name") if isinstance(item, dict) else item)
        if name and name not in result:
            result.append(name)
    return result


def split_values(value: Any) -> list[str]:
    """Split a comma-separated value into unique trimmed strings."""
    text = clean_text(value)
    if not text:
        return []
    result: list[str] = []
    for item in text.split(","):
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


def mood_tags_for(genres: list[str]) -> list[str]:
    """Assign mood tags when a title contains a mapped genre."""
    genre_set = {genre.casefold() for genre in genres}
    return [
        tag for tag, mapped in MOOD_TAGS.items()
        if genre_set.intersection({genre.casefold() for genre in mapped})
    ]


def integer_or_none(value: Any) -> int | None:
    """Convert a numeric value to int, treating missing and zero as None."""
    if is_missing(value):
        return None
    number = int(float(value))
    return number or None


def number_or_none(value: Any) -> float | None:
    """Convert a numeric value to float, treating missing values as None."""
    return None if is_missing(value) else float(value)


def year_from(value: Any) -> int | None:
    """Extract the first four-digit year from a date or season string."""
    text = clean_text(value)
    match = re.search(r"(?:19|20)\d{2}", text or "")
    return int(match.group()) if match else None


def duration_minutes(value: Any) -> int | None:
    """Extract the first integer minute value from an anime duration."""
    text = clean_text(value)
    match = re.search(r"(\d+)\s*min", text or "", flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def crew_director(value: Any) -> str | None:
    """Return the first crew member whose job is Director."""
    for member in parse_json_array(value):
        if isinstance(member, dict) and clean_text(member.get("job")) == "Director":
            return clean_text(member.get("name"))
    return None


def top_cast(value: Any) -> list[str]:
    """Return up to five cast names ordered by the source order field."""
    cast = [item for item in parse_json_array(value) if isinstance(item, dict)]
    cast.sort(key=lambda item: int(item.get("order", 999999)))
    return [
        name for item in cast
        if (name := clean_text(item.get("name"))) is not None
    ][:5]


def movie_document(row: pd.Series) -> dict[str, Any]:
    """Build one normalized movie document from a merged CSV row."""
    genres = named_values(row["genres"])
    title = clean_text(row["title"])
    original_title = clean_text(row["original_title"])
    return {
        "_id": f"movie:{int(row['id'])}",
        "media_type": "movie",
        "source_id": int(row["id"]),
        "title": title,
        "alt_titles": [original_title] if original_title and original_title != title else [],
        "genres": genres,
        "synopsis": clean_text(row["overview"]),
        "year": year_from(row["release_date"]),
        "rating": float(row["vote_average"]),
        "votes": int(row["vote_count"]),
        "popularity": number_or_none(row["popularity"]),
        "language": clean_text(row["original_language"]),
        "poster_url": None,
        "status": clean_text(row["status"]),
        "mood_tags": mood_tags_for(genres),
        "movie": {
            "runtime": integer_or_none(row["runtime"]),
            "budget": integer_or_none(row["budget"]),
            "revenue": integer_or_none(row["revenue"]),
            "tagline": clean_text(row["tagline"]),
            "director": crew_director(row["crew"]),
            "cast": top_cast(row["cast"]),
            "keywords": named_values(row["keywords"]),
            "companies": named_values(row["production_companies"]),
            "countries": named_values(row["production_countries"]),
        },
    }


def anime_document(row: pd.Series) -> dict[str, Any]:
    """Build one normalized anime document from a CSV row."""
    title = clean_text(row["title"])
    genres = split_values(row["genre"])
    alt_titles: list[str] = []
    for value in [row["title_english"], row["title_japanese"], row["title_synonyms"]]:
        values = split_values(value)
        if not values:
            text = clean_text(value)
            values = [text] if text else []
        for alt_title in values:
            if alt_title != title and alt_title not in alt_titles:
                alt_titles.append(alt_title)
    airing = clean_text(row["airing"])
    return {
        "_id": f"anime:{int(row['anime_id'])}",
        "media_type": "anime",
        "source_id": int(row["anime_id"]),
        "title": title,
        "alt_titles": alt_titles,
        "genres": genres,
        "synopsis": clean_text(row["background"]),
        "year": year_from(row["aired_string"]) or year_from(row["premiered"]),
        "rating": float(row["score"]),
        "votes": integer_or_none(row["scored_by"]),
        "popularity": number_or_none(row["popularity"]),
        "language": None,
        "poster_url": clean_text(row["image_url"]),
        "status": clean_text(row["status"]),
        "mood_tags": mood_tags_for(genres),
        "anime": {
            "type": clean_text(row["type"]),
            "episodes": integer_or_none(row["episodes"]),
            "studios": split_values(row["studio"]),
            "producers": split_values(row["producer"]),
            "source": clean_text(row["source"]),
            "premiered": clean_text(row["premiered"]),
            "duration_minutes": duration_minutes(row["duration"]),
            "age_rating": clean_text(row["rating"]),
            "rank": integer_or_none(row["rank"]),
            "members": integer_or_none(row["members"]),
            "favorites": integer_or_none(row["favorites"]),
            "airing": airing.casefold() == "true" if airing else False,
        },
    }


def insert_in_batches(documents: list[dict[str, Any]]) -> int:
    """Insert documents in batches and return the number inserted."""
    inserted = 0
    collection = db["titles"]
    for start in range(0, len(documents), BATCH_SIZE):
        result = collection.insert_many(documents[start:start + BATCH_SIZE], ordered=False)
        inserted += len(result.inserted_ids)
    return inserted


def load_data() -> None:
    """Load cleaned movies and anime into a freshly created titles collection."""
    data_dir = ROOT / "data"
    dropped: Counter[str] = Counter()
    rows_read = {"movie": 0, "anime": 0}
    documents: list[dict[str, Any]] = []

    movies = pd.read_csv(data_dir / "movies.csv", low_memory=False)
    credits = pd.read_csv(data_dir / "credits.csv", low_memory=False)
    anime = pd.read_csv(data_dir / "anime.csv", low_memory=False)
    merged = movies.merge(
        credits[["movie_id", "cast", "crew"]],
        left_on="id",
        right_on="movie_id",
        how="left",
    )

    rows_read["movie"] = len(merged)
    seen_movie_ids: set[int] = set()
    for _, row in merged.iterrows():
        if not clean_text(row["title"]):
            dropped["movie: missing title"] += 1
        elif is_missing(row["vote_average"]):
            dropped["movie: missing rating"] += 1
        elif is_missing(row["vote_count"]) or int(float(row["vote_count"])) < 10:
            dropped["movie: vote_count < 10"] += 1
        elif int(row["id"]) in seen_movie_ids:
            dropped["movie: duplicate id"] += 1
        else:
            seen_movie_ids.add(int(row["id"]))
            documents.append(movie_document(row))

    rows_read["anime"] = len(anime)
    seen_anime_ids: set[int] = set()
    for _, row in anime.iterrows():
        genres = split_values(row["genre"])
        anime_id = int(row["anime_id"])
        if not clean_text(row["title"]):
            dropped["anime: missing title"] += 1
        elif is_missing(row["score"]):
            dropped["anime: missing rating"] += 1
        elif anime_id in seen_anime_ids:
            dropped["anime: duplicate id"] += 1
        elif EXCLUDE_ADULT and any(g.casefold() == "hentai" for g in genres):
            dropped["anime: Hentai excluded"] += 1
        else:
            seen_anime_ids.add(anime_id)
            documents.append(anime_document(row))

    print("WARNING: dropping and recreating the 'titles' collection.")
    if "titles" in db.list_collection_names():
        db["titles"].drop()
    db.create_collection("titles", validator=VALIDATOR)

    inserted = insert_in_batches(documents)
    collection = db["titles"]
    counts = {
        "movie": collection.count_documents({"media_type": "movie"}),
        "anime": collection.count_documents({"media_type": "anime"}),
    }
    print("\nLoad summary")
    print(f"Rows read: movies={rows_read['movie']}, anime={rows_read['anime']}")
    print("Rows dropped:")
    for reason, count in sorted(dropped.items()):
        print(f"  - {reason}: {count}")
    if not dropped:
        print("  - none")
    print(f"Rows inserted: total={inserted}")
    print(f"  - movie: {counts['movie']}")
    print(f"  - anime: {counts['anime']}")
    print("\nVerified collection counts:", counts)
    print("\nSample documents:")
    for sample in collection.find().limit(2):
        pprint(sample)


if __name__ == "__main__":
    try:
        load_data()
    except Exception as exc:
        print(f"ERROR: data load failed: {exc}", file=sys.stderr)
        raise