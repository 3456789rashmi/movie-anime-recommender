"""MongoDB connection, title queries, and user data access."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

load_dotenv()

_MONGO_URI = os.getenv("MONGO_URI")
_DB_NAME = os.getenv("DB_NAME", "media_recommender")
if not _MONGO_URI:
    raise RuntimeError("MONGO_URI is not configured in .env")

client = MongoClient(_MONGO_URI)
db = client[_DB_NAME]

VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["media_type", "title", "rating"],
        "properties": {
            "media_type": {"enum": ["movie", "anime"]},
            "title": {"bsonType": "string", "minLength": 1},
            "rating": {
                "bsonType": ["double", "int", "long", "decimal"],
                "minimum": 0,
                "maximum": 10,
            },
        },
    }
}

_SORT_FIELDS = {
    "rating": ("rating", DESCENDING),
    "popularity": ("popularity", DESCENDING),
    "year": ("year", DESCENDING),
    "votes": ("votes", DESCENDING),
    "title": ("title", ASCENDING),
}


def get_db() -> Database:
    """Return the configured MongoDB database."""
    return db


def get_titles() -> Collection:
    """Return the unified titles collection."""
    return db["titles"]


def _without_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove MongoDB's internal identifier from an API-friendly document."""
    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result


def search_titles(
    query: str = "",
    media_type: str | None = None,
    genres: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    min_rating: float | None = None,
    sort_by: str = "rating",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """Search, filter, sort, and paginate title documents."""
    if media_type is not None and media_type not in {"movie", "anime"}:
        raise ValueError("media_type must be 'movie', 'anime', or None")
    if sort_by not in _SORT_FIELDS:
        raise ValueError(f"sort_by must be one of: {', '.join(_SORT_FIELDS)}")
    if page < 1 or page_size < 1:
        raise ValueError("page and page_size must be positive integers")
    if year_range is not None:
        if len(year_range) != 2 or year_range[0] > year_range[1]:
            raise ValueError("year_range must be a (start_year, end_year) tuple")

    filters: dict[str, Any] = {}
    if query and query.strip():
        filters["$text"] = {"$search": query.strip()}
    if media_type:
        filters["media_type"] = media_type
    if genres:
        filters["genres"] = {"$all": genres}
    if year_range:
        filters["year"] = {"$gte": year_range[0], "$lte": year_range[1]}
    if min_rating is not None:
        if not 0 <= min_rating <= 10:
            raise ValueError("min_rating must be between 0 and 10")
        filters["rating"] = {"$gte": min_rating}

    collection = get_titles()
    total = collection.count_documents(filters)
    sort_field, direction = _SORT_FIELDS[sort_by]
    cursor = (
        collection.find(filters, {"_id": 0})
        .sort(sort_field, direction)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "results": list(cursor),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_title(media_type: str, source_id: int) -> dict[str, Any] | None:
    """Return one title by its source media type and original ID."""
    return _without_id(
        get_titles().find_one(
            {"media_type": media_type, "source_id": int(source_id)},
            {"_id": 0},
        )
    )


def get_all_genres(media_type: str | None = None) -> list[str]:
    """Return sorted distinct genres, optionally limited to one media type."""
    match = {"media_type": media_type} if media_type else {}
    pipeline = [
        {"$match": match},
        {"$unwind": "$genres"},
        {"$group": {"_id": "$genres"}},
        {"$sort": {"_id": 1}},
    ]
    return [row["_id"] for row in get_titles().aggregate(pipeline)]


def home_stats() -> dict[str, int]:
    """Return live collection totals for the Streamlit home page."""
    pipeline = [
        {"$facet": {
            "totals": [{"$count": "total"}],
            "media": [{"$group": {"_id": "$media_type", "count": {"$sum": 1}}}],
            "genres": [
                {"$unwind": "$genres"},
                {"$group": {"_id": "$genres"}},
                {"$count": "total"},
            ],
        }},
        {"$project": {
            "total_titles": {"$ifNull": [{"$arrayElemAt": ["$totals.total", 0]}, 0]},
            "total_genres": {"$ifNull": [{"$arrayElemAt": ["$genres.total", 0]}, 0]},
            "media": 1,
        }},
    ]
    result = list(get_titles().aggregate(pipeline))
    if not result:
        return {"total_titles": 0, "movies": 0, "anime": 0, "total_genres": 0}
    stats = result[0]
    counts = {item["_id"]: item["count"] for item in stats["media"]}
    return {
        "total_titles": stats["total_titles"],
        "movies": counts.get("movie", 0),
        "anime": counts.get("anime", 0),
        "total_genres": stats["total_genres"],
    }


def _user_view(user: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a user document without the internal MongoDB identifier."""
    return _without_id(user)


def create_user(username: str) -> dict[str, Any]:
    """Create a user with empty watchlist, ratings, and favorite genres."""
    username = username.strip()
    if not username:
        raise ValueError("username cannot be empty")
    document = {
        "username": username,
        "created_at": datetime.now(timezone.utc),
        "watchlist": [],
        "ratings": [],
        "favorite_genres": [],
    }
    try:
        result = db["users"].insert_one(document)
    except DuplicateKeyError as exc:
        raise ValueError(f"Username already exists: {username}") from exc
    except PyMongoError as exc:
        raise RuntimeError(f"Could not create user '{username}': {exc}") from exc
    document["_id"] = result.inserted_id
    return _user_view(document) or {}


def get_user(username: str) -> dict[str, Any] | None:
    """Return a user by unique username."""
    return _user_view(db["users"].find_one({"username": username}, {"_id": 0}))


def list_usernames() -> list[str]:
    """Return usernames for profile selection."""
    return sorted(db["users"].distinct("username"))


def find_title_by_name(title: str) -> dict[str, Any] | None:
    """Find one title by its display title for profile rating forms."""
    return _without_id(
        get_titles().find_one(
            {"title": title},
            {"_id": 0, "title": 1, "media_type": 1, "source_id": 1},
        )
    )


def add_to_watchlist(username: str, title_id: str) -> bool:
    """Add a title ID to a user's watchlist if it is not already present."""
    result = db["users"].update_one(
        {"username": username},
        {"$addToSet": {"watchlist": title_id}},
    )
    if result.matched_count == 0:
        raise ValueError(f"User not found: {username}")
    return result.modified_count > 0


def remove_from_watchlist(username: str, title_id: str) -> bool:
    """Remove a title ID from a user's watchlist."""
    result = db["users"].update_one(
        {"username": username},
        {"$pull": {"watchlist": title_id}},
    )
    if result.matched_count == 0:
        raise ValueError(f"User not found: {username}")
    return result.modified_count > 0


def rate_title(
    username: str,
    title_id: str,
    rating: float,
    rated_at: datetime | None = None,
) -> bool:
    """Insert or replace one embedded title rating for a user."""
    if not 0 <= rating <= 10:
        raise ValueError("rating must be between 0 and 10")
    rated_at = rated_at or datetime.now(timezone.utc)
    result = db["users"].update_one(
        {"username": username},
        [{
            "$set": {
                "ratings": {
                    "$concatArrays": [
                        {
                            "$filter": {
                                "input": {"$ifNull": ["$ratings", []]},
                                "as": "existing_rating",
                                "cond": {
                                    "$ne": ["$$existing_rating.title_id", title_id]
                                },
                            }
                        },
                        [{"title_id": title_id, "rating": float(rating), "rated_at": rated_at}],
                    ]
                },
                "updated_at": datetime.now(timezone.utc),
            }
        }],
    )
    if result.matched_count == 0:
        raise ValueError(f"User not found: {username}")
    return True


def delete_user(username: str) -> bool:
    """Delete a user by username and return whether a document was deleted."""
    result = db["users"].delete_one({"username": username})
    return result.deleted_count == 1


def similar_titles(
    media_type: str,
    source_id: int,
    limit: int = 10,
    cross_media: bool = True,
) -> list[dict[str, Any]]:
    """Find titles similar by genres, rating, keywords, and mood tags."""
    if media_type not in {"movie", "anime"}:
        raise ValueError("media_type must be 'movie' or 'anime'")
    if limit < 1:
        raise ValueError("limit must be positive")
    media_match_expression = (
        {"$ne": ["$media_type", media_type]}
        if cross_media
        else {"$eq": ["$media_type", media_type]}
    )
    pipeline = [
        # Select the source title and make missing feature arrays safe.
        {"$match": {"media_type": media_type, "source_id": int(source_id)}},
        # Keep one source document while the lookup compares every candidate.
        {"$limit": 1},
        # Compare candidates inside MongoDB using the source title variables.
        {
            "$lookup": {
                "from": "titles",
                "let": {
                    "source_id": "$source_id",
                    "source_type": "$media_type",
                    "source_genres": {"$ifNull": ["$genres", []]},
                    "source_rating": "$rating",
                    "source_features": {
                        "$setUnion": [
                            {"$ifNull": ["$mood_tags", []]},
                            {"$ifNull": ["$movie.keywords", []]},
                        ]
                    },
                },
                "pipeline": [
                    # Restrict candidates to the requested media relationship.
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$ne": ["$source_id", "$$source_id"]},
                                    media_match_expression,
                                ]
                            }
                        }
                    },
                    # Normalize candidate arrays before set arithmetic.
                    {
                        "$set": {
                            "candidate_genres": {"$ifNull": ["$genres", []]},
                            "candidate_features": {
                                "$setUnion": [
                                    {"$ifNull": ["$mood_tags", []]},
                                    {"$ifNull": ["$movie.keywords", []]},
                                ]
                            },
                        }
                    },
                    # Calculate the three requested overlap components.
                    {
                        "$set": {
                            "shared_genre_count": {
                                "$size": {
                                    "$setIntersection": [
                                        "$candidate_genres",
                                        "$$source_genres",
                                    ]
                                }
                            },
                            "genre_union_count": {
                                "$size": {
                                    "$setUnion": [
                                        "$candidate_genres",
                                        "$$source_genres",
                                    ]
                                }
                            },
                            "feature_overlap_count": {
                                "$size": {
                                    "$setIntersection": [
                                        "$candidate_features",
                                        "$$source_features",
                                    ]
                                }
                            },
                            "feature_union_count": {
                                "$size": {
                                    "$setUnion": [
                                        "$candidate_features",
                                        "$$source_features",
                                    ]
                                }
                            },
                        }
                    },
                    # Combine genre, rating, and feature similarity into one score.
                    {
                        "$set": {
                            "similarity_score": {
                                "$add": [
                                    {
                                        "$multiply": [
                                            {
                                                "$cond": [
                                                    {"$gt": ["$genre_union_count", 0]},
                                                    {
                                                        "$divide": [
                                                            "$shared_genre_count",
                                                            "$genre_union_count",
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            0.6,
                                        ]
                                    },
                                    {
                                        "$multiply": [
                                            {
                                                "$subtract": [
                                                    1,
                                                    {
                                                        "$divide": [
                                                            {
                                                                "$abs": {
                                                                    "$subtract": [
                                                                        "$rating",
                                                                        "$$source_rating",
                                                                    ]
                                                                }
                                                            },
                                                            10,
                                                        ]
                                                    },
                                                ]
                                            },
                                            0.2,
                                        ]
                                    },
                                    {
                                        "$multiply": [
                                            {
                                                "$cond": [
                                                    {"$gt": ["$feature_union_count", 0]},
                                                    {
                                                        "$divide": [
                                                            "$feature_overlap_count",
                                                            "$feature_union_count",
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            0.2,
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    # Rank the most similar candidates first.
                    {"$sort": {"similarity_score": -1, "rating": -1}},
                    # Return only the requested number of recommendations.
                    {"$limit": limit},
                    # Hide temporary arithmetic fields and MongoDB's identifier.
                    {
                        "$project": {
                            "_id": 0,
                            "candidate_genres": 0,
                            "candidate_features": 0,
                            "shared_genre_count": 0,
                            "genre_union_count": 0,
                            "feature_overlap_count": 0,
                            "feature_union_count": 0,
                        }
                    },
                ],
                "as": "recommendations",
            }
        },
        # Turn the lookup array into one result document per recommendation.
        {"$unwind": "$recommendations"},
        # Return only the candidate title documents.
        {"$replaceWith": "$recommendations"},
    ]
    return list(get_titles().aggregate(pipeline))


def mood_recommendations(
    mood: str,
    media_type: str | None = None,
    min_votes: int = 0,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Rank mood-tagged titles with a Bayesian weighted rating."""
    if media_type is not None and media_type not in {"movie", "anime"}:
        raise ValueError("media_type must be 'movie', 'anime', or None")
    if min_votes < 0 or limit < 1:
        raise ValueError("min_votes must be non-negative and limit positive")
    match: dict[str, Any] = {"mood_tags": mood, "votes": {"$gte": min_votes}}
    if media_type:
        match["media_type"] = media_type
    pipeline = [
        # Select titles carrying the requested mood and vote minimum.
        {"$match": match},
        # Calculate the global average rating and retain matching documents.
        {
            "$group": {
                "_id": None,
                "C": {"$avg": "$rating"},
                "documents": {"$push": "$$ROOT"},
            }
        },
        # Expand the saved documents for per-title score calculation.
        {"$unwind": "$documents"},
        # Add the Bayesian average using the supplied vote prior.
        {
            "$set": {
                "documents.bayesian_score": {
                    "$add": [
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        "$documents.votes",
                                        {"$add": ["$documents.votes", 100]},
                                    ]
                                },
                                "$documents.rating",
                            ]
                        },
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        100,
                                        {"$add": ["$documents.votes", 100]},
                                    ]
                                },
                                "$C",
                            ]
                        },
                    ]
                }
            }
        },
        # Rank recommendations by their Bayesian score.
        {"$sort": {"documents.bayesian_score": -1, "documents.votes": -1}},
        # Apply the requested result limit.
        {"$limit": limit},
        # Return clean title documents with the calculated score.
        {"$replaceWith": "$documents"},
        # Remove MongoDB's internal identifier from API results.
        {"$project": {"_id": 0}},
    ]
    return list(get_titles().aggregate(pipeline))


def hidden_gems(
    media_type: str | None = None,
    min_rating: float = 7.5,
    max_votes_percentile: float = 25,
) -> list[dict[str, Any]]:
    """Find highly rated titles at or below a vote-count percentile."""
    if media_type is not None and media_type not in {"movie", "anime"}:
        raise ValueError("media_type must be 'movie', 'anime', or None")
    if not 0 <= max_votes_percentile <= 100:
        raise ValueError("max_votes_percentile must be between 0 and 100")
    match: dict[str, Any] = {"rating": {"$gte": min_rating}}
    if media_type:
        match["media_type"] = media_type
    percentile = max_votes_percentile / 100
    pipeline = [
        # Restrict the population to highly rated titles.
        {"$match": match},
        # Compute the requested vote-count percentile and retain all titles.
        {
            "$group": {
                "_id": None,
                "vote_threshold": {
                    "$percentile": {
                        "input": "$votes",
                        "p": [percentile],
                        "method": "approximate",
                    }
                },
                "documents": {"$push": "$$ROOT"},
            }
        },
        # Expand the population for threshold filtering.
        {"$unwind": "$documents"},
        # Keep titles at or below the low-vote threshold.
        {
            "$match": {
                "$expr": {
                    "$lte": [
                        "$documents.votes",
                        {"$arrayElemAt": ["$vote_threshold", 0]},
                    ]
                }
            }
        },
        # Show the best-rated hidden gems first.
        {"$sort": {"documents.rating": -1, "documents.votes": 1}},
        # Return clean title documents.
        {"$replaceWith": "$documents"},
        # Remove MongoDB's internal identifier from API results.
        {"$project": {"_id": 0}},
    ]
    return list(get_titles().aggregate(pipeline))


def top_by_genre_per_year(
    genre: str | None = None,
    media_type: str | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Rank the highest-rated titles within each genre and year."""
    if media_type is not None and media_type not in {"movie", "anime"}:
        raise ValueError("media_type must be 'movie', 'anime', or None")
    if limit < 1:
        raise ValueError("limit must be positive")
    match: dict[str, Any] = {"year": {"$ne": None}}
    if genre:
        match["genres"] = genre
    if media_type:
        match["media_type"] = media_type
    pipeline = [
        # Keep titles with a usable year and optional filters.
        {"$match": match},
        # Create one ranking row for every title-genre membership.
        {"$unwind": "$genres"},
        # Rank titles by rating and votes inside each genre/year partition.
        {
            "$setWindowFields": {
                "partitionBy": {"genre": "$genres", "year": "$year"},
                "sortBy": {"rating": -1},
                "output": {"rank": {"$rank": {}}},
            }
        },
        # Keep the requested number of titles per genre and year.
        {"$match": {"rank": {"$lte": limit}}},
        # Sort the report into a readable genre/year order.
        {"$sort": {"genres": 1, "year": -1, "rank": 1}},
        # Return report fields without MongoDB's internal identifier.
        {
            "$project": {
                "_id": 0,
                "genre": "$genres",
                "year": 1,
                "rank": 1,
                "media_type": 1,
                "source_id": 1,
                "title": 1,
                "rating": 1,
                "votes": 1,
            }
        },
    ]
    return list(get_titles().aggregate(pipeline))


def genre_counts(media_type: str | None = None) -> list[dict[str, Any]]:
    """Count titles in each genre."""
    match = {"media_type": media_type} if media_type else {}
    pipeline = [
        # Restrict the media type when requested.
        {"$match": match},
        # Make each genre available to the grouping stage.
        {"$unwind": "$genres"},
        # Count titles by genre.
        {"$group": {"_id": "$genres", "count": {"$sum": 1}}},
        # Put the most common genres first.
        {"$sort": {"count": -1, "_id": 1}},
        # Use a named genre field and hide the internal identifier.
        {"$project": {"_id": 0, "genre": "$_id", "count": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def avg_rating_by_year(media_type: str | None = None) -> list[dict[str, Any]]:
    """Calculate average rating and title count for each year."""
    match: dict[str, Any] = {"year": {"$ne": None}}
    if media_type:
        match["media_type"] = media_type
    pipeline = [
        # Keep documents with a year and optional media filter.
        {"$match": match},
        # Aggregate title count and average rating by year.
        {
            "$group": {
                "_id": "$year",
                "average_rating": {"$avg": "$rating"},
                "title_count": {"$sum": 1},
            }
        },
        # Present years chronologically.
        {"$sort": {"_id": 1}},
        # Return a clean analytics shape.
        {"$project": {"_id": 0, "year": "$_id", "average_rating": 1, "title_count": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def rating_distribution(
    media_type: str | None = None,
    bucket_count: int = 10,
) -> list[dict[str, Any]]:
    """Return a rating histogram using MongoDB's $bucket stage."""
    if bucket_count < 1:
        raise ValueError("bucket_count must be positive")
    match = {"media_type": media_type} if media_type else {}
    boundaries = [10 * index / bucket_count for index in range(bucket_count + 1)]
    pipeline = [
        # Restrict the population to the requested media type.
        {"$match": match},
        # Place ratings into evenly spaced 0-10 buckets.
        {
            "$bucket": {
                "groupBy": "$rating",
                "boundaries": boundaries,
                "default": "other",
                "output": {"count": {"$sum": 1}},
            }
        },
        # Return the bucket lower bound as a readable field.
        {"$project": {"_id": 0, "rating_from": "$_id", "count": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def top_studios(limit: int = 10) -> list[dict[str, Any]]:
    """Return anime studios ranked by the number of titles."""
    if limit < 1:
        raise ValueError("limit must be positive")
    pipeline = [
        # Restrict analytics to anime documents.
        {"$match": {"media_type": "anime"}},
        # Make each studio independently countable.
        {"$unwind": "$anime.studios"},
        # Count anime titles for each studio.
        {"$group": {"_id": "$anime.studios", "title_count": {"$sum": 1}}},
        # Rank the most prolific studios first.
        {"$sort": {"title_count": -1, "_id": 1}},
        # Return the requested number of studios.
        {"$limit": limit},
        # Return a clean analytics shape.
        {"$project": {"_id": 0, "studio": "$_id", "title_count": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def top_directors(limit: int = 10) -> list[dict[str, Any]]:
    """Return movie directors ranked by title count and average rating."""
    if limit < 1:
        raise ValueError("limit must be positive")
    pipeline = [
        # Restrict analytics to movie documents with a director.
        {"$match": {"media_type": "movie", "movie.director": {"$nin": [None, ""]}}},
        # Group movies by director.
        {
            "$group": {
                "_id": "$movie.director",
                "title_count": {"$sum": 1},
                "average_rating": {"$avg": "$rating"},
            }
        },
        # Rank directors by catalogue size and rating.
        {"$sort": {"title_count": -1, "average_rating": -1}},
        # Return only the requested directors.
        {"$limit": limit},
        # Return a clean analytics shape.
        {"$project": {"_id": 0, "director": "$_id", "title_count": 1, "average_rating": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def media_type_comparison() -> list[dict[str, Any]]:
    """Compare movie and anime distributions with one $facet pipeline."""
    pipeline = [
        # Run independent movie and anime reports over the same collection.
        {
            "$facet": {
                "by_media_type": [
                    # Group overall count and average rating by media type.
                    {
                        "$group": {
                            "_id": "$media_type",
                            "title_count": {"$sum": 1},
                            "average_rating": {"$avg": "$rating"},
                            "average_votes": {"$avg": "$votes"},
                        }
                    },
                    # Sort the comparison consistently.
                    {"$sort": {"_id": 1}},
                    # Return named media types without internal IDs.
                    {
                        "$project": {
                            "_id": 0,
                            "media_type": "$_id",
                            "title_count": 1,
                            "average_rating": 1,
                            "average_votes": 1,
                        }
                    },
                ],
                "rating_buckets": [
                    # Bucket ratings to compare the two media distributions.
                    {
                        "$bucket": {
                            "groupBy": "$rating",
                            "boundaries": [0, 2, 4, 6, 8, 10.01],
                            "default": "other",
                            "output": {"count": {"$sum": 1}},
                        }
                    },
                    # Return readable rating bucket boundaries.
                    {"$project": {"_id": 0, "rating_from": "$_id", "count": 1}},
                ],
            }
        },
        # Return one comparison object containing both facet reports.
        {"$project": {"_id": 0, "by_media_type": 1, "rating_buckets": 1}},
    ]
    return list(get_titles().aggregate(pipeline))


def taste_profile(username: str) -> dict[str, Any]:
    """Aggregate a user's rated titles into a weighted taste profile."""
    pipeline = [
        # Select the requested user document.
        {"$match": {"username": username}},
        # Turn each embedded user rating into a separate aggregation row.
        {"$unwind": "$ratings"},
        # Join each rating to its title document using the title string ID.
        {
            "$lookup": {
                "from": "titles",
                "let": {"title_id": "$ratings.title_id"},
                "pipeline": [
                    # Match the title referenced by this user rating.
                    {"$match": {"$expr": {"$eq": ["$_id", "$$title_id"]}}},
                    # Keep only fields needed to build the taste profile.
                    {
                        "$project": {
                            "_id": 0,
                            "title": 1,
                            "media_type": 1,
                            "genres": 1,
                        }
                    },
                ],
                "as": "rated_title",
            }
        },
        # Convert the one-element lookup result into a title object.
        {"$unwind": "$rated_title"},
        # Build independent genre, rating, and media-type profile reports.
        {
            "$facet": {
                "genres": [
                    # Give each genre from each rated title its user rating weight.
                    {"$unwind": "$rated_title.genres"},
                    # Sum user ratings and count supporting rated titles by genre.
                    {
                        "$group": {
                            "_id": "$rated_title.genres",
                            "weighted_score": {"$sum": "$ratings.rating"},
                            "rated_title_count": {"$sum": 1},
                        }
                    },
                    # Rank genres by the user's weighted preference.
                    {"$sort": {"weighted_score": -1, "rated_title_count": -1}},
                    # Return a clean favorite-genre record.
                    {
                        "$project": {
                            "_id": 0,
                            "genre": "$_id",
                            "weighted_score": 1,
                            "rated_title_count": 1,
                        }
                    },
                ],
                "summary": [
                    # Calculate the average rating this user gives titles.
                    {
                        "$group": {
                            "_id": None,
                            "average_rating_given": {"$avg": "$ratings.rating"},
                            "rated_title_count": {"$sum": 1},
                        }
                    },
                    # Remove the temporary group identifier.
                    {"$project": {"_id": 0}},
                ],
                "media_types": [
                    # Count ratings and average user scores by media type.
                    {
                        "$group": {
                            "_id": "$rated_title.media_type",
                            "rated_title_count": {"$sum": 1},
                            "average_rating_given": {"$avg": "$ratings.rating"},
                        }
                    },
                    # Return media type as a named field.
                    {
                        "$project": {
                            "_id": 0,
                            "media_type": "$_id",
                            "rated_title_count": 1,
                            "average_rating_given": 1,
                        }
                    },
                    # Keep the split stable for display.
                    {"$sort": {"media_type": 1}},
                ],
            }
        },
        # Flatten the single summary row into the final profile object.
        {
            "$project": {
                "_id": 0,
                "favorite_genres": "$genres",
                "summary": {"$arrayElemAt": ["$summary", 0]},
                "preferred_media_type_split": "$media_types",
            }
        },
    ]
    result = list(db["users"].aggregate(pipeline))
    if not result:
        if get_user(username) is None:
            raise ValueError(f"User not found: {username}")
        return {
            "favorite_genres": [],
            "summary": {
                "average_rating_given": None,
                "rated_title_count": 0,
            },
            "preferred_media_type_split": [],
        }
    profile = result[0]
    profile["username"] = username
    return profile


def personalized_recommendations(
    username: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Recommend unseen titles using a MongoDB-computed taste profile."""
    if limit < 1:
        raise ValueError("limit must be positive")
    pipeline = [
        # Select the user whose ratings define the recommendation profile.
        {"$match": {"username": username}},
        # Normalize watchlist and rating IDs for exclusion checks.
        {
            "$set": {
                "excluded_ids": {
                    "$setUnion": [
                        {"$ifNull": ["$watchlist", []]},
                        {
                            "$map": {
                                "input": {"$ifNull": ["$ratings", []]},
                                "as": "rating",
                                "in": "$$rating.title_id",
                            }
                        },
                    ]
                }
            }
        },
        # Join all titles rated by this user for overlap and explanation data.
        {
            "$lookup": {
                "from": "titles",
                "let": {"rated_ids": "$ratings.title_id"},
                "pipeline": [
                    # Keep only titles whose string IDs were rated by the user.
                    {"$match": {"$expr": {"$in": ["$_id", "$$rated_ids"]}}},
                    # Retain title genres and name for scoring and explanations.
                    {"$project": {"_id": 1, "title": 1, "genres": 1}},
                ],
                "as": "rated_titles",
            }
        },
        # Attach each user's numeric rating to its joined title document.
        {
            "$set": {
                "rated_titles_with_scores": {
                    "$map": {
                        "input": "$rated_titles",
                        "as": "rated_title",
                        "in": {
                            "$mergeObjects": [
                                "$$rated_title",
                                {
                                    "user_rating": {
                                        "$let": {
                                            "vars": {
                                                "matching_rating": {
                                                    "$arrayElemAt": [
                                                        {
                                                            "$filter": {
                                                                "input": "$ratings",
                                                                "as": "rating",
                                                                "cond": {
                                                                    "$eq": [
                                                                        "$$rating.title_id",
                                                                        "$$rated_title._id",
                                                                    ]
                                                                },
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                }
                                            },
                                            "in": "$$matching_rating.rating",
                                        }
                                    }
                                },
                            ]
                        },
                    }
                }
            }
        },
        # Generate candidate recommendations from the complete titles collection.
        {
            "$lookup": {
                "from": "titles",
                "let": {
                    "excluded_ids": "$excluded_ids",
                    "rated_titles": "$rated_titles_with_scores",
                },
                "pipeline": [
                    # Exclude titles already watched, rated, or saved.
                    {
                        "$match": {
                            "$expr": {"$not": [{"$in": ["$_id", "$$excluded_ids"]}]}
                        }
                    },
                    # Calculate the global rating prior for Bayesian scoring.
                    {
                        "$setWindowFields": {
                            "output": {
                                "global_average_rating": {
                                    "$avg": "$rating",
                                    "window": {
                                        "documents": ["unbounded", "unbounded"]
                                    },
                                }
                            }
                        }
                    },
                    # Calculate weighted genre overlap and explanation candidates.
                    {
                        "$set": {
                            "genre_weighted_overlap": {
                                "$reduce": {
                                    "input": "$$rated_titles",
                                    "initialValue": 0,
                                    "in": {
                                        "$add": [
                                            "$$value",
                                            {
                                                "$multiply": [
                                                    {
                                                        "$size": {
                                                            "$setIntersection": [
                                                                {"$ifNull": ["$genres", []]},
                                                                {"$ifNull": ["$$this.genres", []]},
                                                            ]
                                                        }
                                                    },
                                                    "$$this.user_rating",
                                                ]
                                            },
                                        ]
                                    },
                                }
                            },
                            "reason_candidates": {
                                "$map": {
                                    "input": "$$rated_titles",
                                    "as": "rated_title",
                                    "in": {
                                        "title": "$$rated_title.title",
                                        "shared_genres": {
                                            "$size": {
                                                "$setIntersection": [
                                                    {"$ifNull": ["$genres", []]},
                                                    {"$ifNull": ["$$rated_title.genres", []]},
                                                ]
                                            }
                                        },
                                        "user_rating": "$$rated_title.user_rating",
                                    },
                                }
                            },
                        }
                    },
                    # Require at least one genre match with the user's profile.
                    {"$match": {"genre_weighted_overlap": {"$gt": 0}}},
                    # Convert weighted overlap and Bayesian rating into one score.
                    {
                        "$set": {
                            "genre_score": {
                                "$divide": [
                                    "$genre_weighted_overlap",
                                    {
                                        "$max": [
                                            1,
                                            {
                                                "$multiply": [
                                                    {"$size": {"$ifNull": ["$genres", []]}},
                                                    10,
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                            "bayesian_score": {
                                "$add": [
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    "$votes",
                                                    {"$add": ["$votes", 100]},
                                                ]
                                            },
                                            "$rating",
                                        ]
                                    },
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    100,
                                                    {"$add": ["$votes", 100]},
                                                ]
                                            },
                                            "$global_average_rating",
                                        ]
                                    },
                                ]
                            },
                            "sorted_reasons": {
                                "$sortArray": {
                                    "input": "$reason_candidates",
                                    "sortBy": {
                                        "shared_genres": -1,
                                        "user_rating": -1,
                                    },
                                }
                            },
                        }
                    },
                    # Combine taste match and Bayesian quality into final ranking.
                    {
                        "$set": {
                            "personalization_score": {
                                "$add": [
                                    {"$multiply": ["$genre_score", 0.7]},
                                    {"$multiply": ["$bayesian_score", 0.3]},
                                ]
                            },
                            "reason": {
                                "$concat": [
                                    "because you liked ",
                                    {
                                        "$ifNull": [
                                            {"$arrayElemAt": ["$sorted_reasons.title", 0]},
                                            "your highly rated titles",
                                        ]
                                    },
                                ]
                            },
                        }
                    },
                    # Rank the best personalized candidates first.
                    {"$sort": {"personalization_score": -1, "rating": -1}},
                    # Return only the requested recommendations.
                    {"$limit": limit},
                    # Remove implementation-only fields from each result.
                    {
                        "$project": {
                            "_id": 0,
                            "excluded_ids": 0,
                            "rated_titles": 0,
                            "rated_titles_with_scores": 0,
                            "reason_candidates": 0,
                            "sorted_reasons": 0,
                            "genre_weighted_overlap": 0,
                            "genre_score": 0,
                            "bayesian_score": 0,
                            "global_average_rating": 0,
                        }
                    },
                ],
                "as": "recommendations",
            }
        },
        # Expand the candidate array into one result per recommendation.
        {"$unwind": "$recommendations"},
        # Return only recommendation documents, not user state.
        {"$replaceWith": "$recommendations"},
    ]
    result = list(db["users"].aggregate(pipeline))
    if not result and get_user(username) is None:
        raise ValueError(f"User not found: {username}")
    return result


if __name__ == "__main__":
    print(client.server_info()["version"])
    print("Connected to:", db.name)
