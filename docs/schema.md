# Unified MongoDB Schema

The application stores movies and anime in one MongoDB collection named
`titles`. This keeps search, filtering, aggregation, and recommendations
consistent across both media types. Source-specific data is kept in a nested
`movie` or `anime` object instead of being discarded.

The database name comes from `DB_NAME` in `.env` (normally
`media_recommender`). The collection validator is defined as `VALIDATOR` in
[`db.py`](../db.py) and can be passed to PyMongo:

```python
db.create_collection("titles", validator=VALIDATOR)
```

## `users` collection

The `users` collection stores application preferences and interaction history.
It is intentionally separate from `titles`: user documents should not be
duplicated when a title is updated or reloaded.

| Field | BSON type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId or string | MongoDB default | Unique user identifier. |
| `username` | string | yes | Display/login name; unique index recommended. |
| `email` | string | no | Optional contact or login email; unique index recommended when present. |
| `favorite_title_ids` | array of strings | no | `_id` values from `titles` explicitly liked by the user. |
| `ratings` | array of objects | no | User ratings, each containing `title_id`, `rating`, and optional `rated_at`. |
| `preferred_media_types` | array of strings | no | Any combination of `movie` and `anime`. |
| `preferred_genres` | array of strings | no | Genres used to personalize recommendations. |
| `created_at` | date | no | Account creation timestamp. |
| `updated_at` | date | no | Last preference or interaction update timestamp. |

Example:

```javascript
{
  _id: "user:1001",
  username: "student_user",
  email: "student@example.test",
  favorite_title_ids: ["movie:155", "anime:20"],
  ratings: [
    { title_id: "movie:155", rating: 5, rated_at: ISODate("2026-10-18") }
  ],
  preferred_media_types: ["movie", "anime"],
  preferred_genres: ["Action", "Adventure"],
  created_at: ISODate("2026-10-18"),
  updated_at: ISODate("2026-10-19")
}
```

## `titles` document shape

| Field | BSON type | Required | Description |
| --- | --- | --- | --- |
| `_id` | ObjectId or string | MongoDB default | Unique document identifier. |
| `media_type` | string | yes | Either `movie` or `anime`. |
| `source_id` | string or integer | no | Original `movies.id` or `anime.anime_id`. |
| `title` | string | yes | Common display title used by the UI. |
| `title_english` | string | no | English anime title when available. |
| `title_japanese` | string | no | Japanese anime title when available. |
| `genres` | array of strings | no | Normalized genre names. |
| `overview` | string | no | Movie overview or anime `background`; anime has no synopsis column. |
| `rating` | number | yes | Movie `vote_average` or anime `score`. |
| `vote_count` | integer | no | Movie `vote_count` or anime `scored_by`. |
| `popularity` | number | no | Popularity metric from the source dataset. |
| `release_date` | date or string | no | Movie release date; anime aired start date when available. |
| `runtime` | number | no | Movie runtime in minutes. |
| `status` | string | no | Release or airing status. |
| `image_url` | string | no | Anime image URL. |
| `movie` | object | no | Movie-specific fields and credits. |
| `anime` | object | no | Anime-specific fields. |

`rating` is deliberately numeric so a single aggregation can compare both
media types. Anime's text age classification from `rating` in `anime.csv` is
stored as `anime.age_rating` to avoid a type conflict.

## Example movie document

```javascript
{
  _id: "movie:155",
  media_type: "movie",
  source_id: 155,
  title: "The Dark Knight",
  genres: ["Drama", "Action", "Crime", "Thriller"],
  overview: "Batman raises the stakes in his war on crime.",
  rating: 8.2,
  vote_count: 12000,
  popularity: 187.3,
  release_date: "2008-07-16",
  runtime: 152,
  status: "Released",
  movie: {
    original_title: "The Dark Knight",
    original_language: "en",
    tagline: "Why So Serious?",
    budget: 185000000,
    revenue: 1004558444,
    homepage: "https://example.test/dark-knight",
    keywords: ["dc comics", "joker", "Batman"],
    production_companies: ["Warner Bros."],
    production_countries: ["United States of America"],
    spoken_languages: ["English"],
    cast: [{ name: "Christian Bale", character: "Bruce Wayne", order: 0 }],
    crew: [{ name: "Christopher Nolan", job: "Director", department: "Directing" }]
  }
}
```

## Example anime document

```javascript
{
  _id: "anime:20",
  media_type: "anime",
  source_id: 20,
  title: "Naruto",
  title_english: "Naruto",
  title_japanese: "NARUTO -ナルト-",
  genres: ["Action", "Adventure", "Comedy", "Martial Arts"],
  overview: "Moments prior to Naruto Uzumaki's birth...",
  rating: 7.8,
  vote_count: 800000,
  popularity: 100,
  release_date: "2002-10-03",
  status: "Finished Airing",
  image_url: "https://example.test/naruto.jpg",
  anime: {
    type: "TV",
    source: "Manga",
    episodes: 220,
    airing: false,
    aired_string: "Oct 3, 2002 to Feb 8, 2007",
    duration: "23 min per ep",
    age_rating: "PG-13 - Teens 13 or older",
    rank: 100,
    members: 1000000,
    favorites: 50000,
    background: "Moments prior to Naruto Uzumaki's birth...",
    premiered: "Fall 2002",
    broadcast: "Thursdays at 19:30 (JST)",
    title_synonyms: ["NARUTO"],
    producer: ["TV Tokyo"],
    licensor: ["VIZ Media"],
    studio: ["Pierrot"],
    opening_theme: ["Rocks"],
    ending_theme: ["Wind"]
  }
}
```

## Source field mapping

| Unified field | `movies.csv` | `credits.csv` | `anime.csv` |
| --- | --- | --- | --- |
| `source_id` | `id` | `movie_id` (join key) | `anime_id` |
| `title` | `title` | `title` (join/reference) | `title` |
| `title_english` | — | — | `title_english` |
| `title_japanese` | — | — | `title_japanese` |
| `genres` | `genres[].name` | — | `genre` split on commas |
| `overview` | `overview` | — | `background` |
| `rating` | `vote_average` | — | `score` |
| `vote_count` | `vote_count` | — | `scored_by` |
| `popularity` | `popularity` | — | `popularity` |
| `release_date` | `release_date` | — | `aired` start date / `aired_string` |
| `runtime` | `runtime` | — | `duration` kept in `anime.duration` |
| `status` | `status` | — | `status` |
| `image_url` | — | — | `image_url` |
| `movie.*` | All remaining movie fields, including parsed `keywords`, `production_companies`, `production_countries`, and `spoken_languages` | `cast` and `crew` JSON arrays | — |
| `anime.*` | — | — | All remaining anime fields, including `rating` as `age_rating`, `type`, `source`, `episodes`, `airing`, `premiered`, `broadcast`, `related`, `producer`, `licensor`, `studio`, `opening_theme`, and `ending_theme` |

JSON-string columns in the CSV files (`genres`, `keywords`, production
metadata, `cast`, and `crew`) should be parsed before insertion. Missing CSV
values should become `None` or be omitted, never `NaN`.
