"""
recommender.py — Core logic for the VibeFinder 1.0 music recommendation system.

This module implements a content-based filtering approach that compares a user's
taste profile against song attributes to generate personalized recommendations.
"""

import csv
import os


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

def load_songs(filepath: str = None) -> list[dict]:
    """Load songs from a CSV file and return a list of song dictionaries with typed values."""
    if filepath is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(base_dir, "data", "songs.csv")

    songs = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            song = {
                "title":        row["title"].strip(),
                "artist":       row["artist"].strip(),
                "genre":        row["genre"].strip().lower(),
                "mood":         row["mood"].strip().lower(),
                "energy":       float(row["energy"]),
                "tempo_bpm":    int(float(row["tempo_bpm"])),
                "valence":      float(row["valence"]),
                "danceability": float(row["danceability"]),
                "acousticness": float(row["acousticness"]),
            }
            songs.append(song)
    return songs


# ---------------------------------------------------------------------------
# Scoring Logic
# ---------------------------------------------------------------------------

def score_song(user_prefs: dict, song: dict) -> tuple[float, list[str]]:
    """
    Score a single song against the user's taste profile.

    Scoring algorithm (Algorithm Recipe):
      +2.0  — genre match
      +1.0  — mood match
      +1.5  — energy proximity  (1.5 * (1 - |song_energy - target_energy|))
      +1.0  — valence proximity (1.0 * (1 - |song_valence - target_valence|))
      +0.75 — danceability proximity
      +0.75 — acousticness proximity

    Returns:
        (score, reasons) where score is a float and reasons is a list of
        human-readable strings explaining each point contribution.
    """
    score = 0.0
    reasons = []

    # --- Genre match (categorical, binary) ---
    if song["genre"] == user_prefs.get("favorite_genre", "").lower():
        score += 2.0
        reasons.append("genre match (+2.0)")

    # --- Mood match (categorical, binary) ---
    if song["mood"] == user_prefs.get("favorite_mood", "").lower():
        score += 1.0
        reasons.append("mood match (+1.0)")

    # --- Energy proximity ---
    target_energy = user_prefs.get("target_energy", 0.5)
    energy_gap = abs(song["energy"] - target_energy)
    energy_score = round(1.5 * (1.0 - energy_gap), 3)
    score += energy_score
    reasons.append(f"energy proximity (+{energy_score})")

    # --- Valence (happiness) proximity ---
    target_valence = user_prefs.get("target_valence", 0.5)
    valence_gap = abs(song["valence"] - target_valence)
    valence_score = round(1.0 * (1.0 - valence_gap), 3)
    score += valence_score
    reasons.append(f"valence proximity (+{valence_score})")

    # --- Danceability proximity ---
    target_dance = user_prefs.get("target_danceability", 0.5)
    dance_gap = abs(song["danceability"] - target_dance)
    dance_score = round(0.75 * (1.0 - dance_gap), 3)
    score += dance_score
    reasons.append(f"danceability proximity (+{dance_score})")

    # --- Acousticness proximity ---
    target_acoustic = user_prefs.get("target_acousticness", 0.3)
    acoustic_gap = abs(song["acousticness"] - target_acoustic)
    acoustic_score = round(0.75 * (1.0 - acoustic_gap), 3)
    score += acoustic_score
    reasons.append(f"acousticness proximity (+{acoustic_score})")

    return round(score, 3), reasons


# ---------------------------------------------------------------------------
# Recommender
# ---------------------------------------------------------------------------

def recommend_songs(user_prefs: dict, songs: list[dict], k: int = 5) -> list[dict]:
    """
    Rank all songs by relevance to user_prefs and return the top-k results.

    Uses score_song as a judge for every track, then sorts by descending score.
    sorted() is used (instead of .sort()) so the original list is not mutated.

    Returns a list of dicts, each containing the original song data plus
    'score' (float) and 'reasons' (list[str]) keys.
    """
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        entry = dict(song)          # shallow copy — don't mutate original
        entry["score"] = score
        entry["reasons"] = reasons
        scored.append(entry)

    ranked = sorted(scored, key=lambda s: s["score"], reverse=True)
    return ranked[:k]


# ---------------------------------------------------------------------------
# Scoring Mode Variants
# ---------------------------------------------------------------------------

def score_song_genre_first(user_prefs: dict, song: dict) -> tuple[float, list[str]]:
    """Scoring variant that triples the genre weight for genre-first ranking mode."""
    score = 0.0
    reasons = []

    if song["genre"] == user_prefs.get("favorite_genre", "").lower():
        score += 6.0          # 3× normal weight
        reasons.append("genre match — GENRE-FIRST mode (+6.0)")
    if song["mood"] == user_prefs.get("favorite_mood", "").lower():
        score += 1.0
        reasons.append("mood match (+1.0)")

    target_energy = user_prefs.get("target_energy", 0.5)
    energy_score = round(1.5 * (1.0 - abs(song["energy"] - target_energy)), 3)
    score += energy_score
    reasons.append(f"energy proximity (+{energy_score})")

    return round(score, 3), reasons


def score_song_energy_first(user_prefs: dict, song: dict) -> tuple[float, list[str]]:
    """Scoring variant that triples the energy weight for energy-first ranking mode."""
    score = 0.0
    reasons = []

    if song["genre"] == user_prefs.get("favorite_genre", "").lower():
        score += 2.0
        reasons.append("genre match (+2.0)")
    if song["mood"] == user_prefs.get("favorite_mood", "").lower():
        score += 1.0
        reasons.append("mood match (+1.0)")

    target_energy = user_prefs.get("target_energy", 0.5)
    energy_score = round(4.5 * (1.0 - abs(song["energy"] - target_energy)), 3)   # 3× weight
    score += energy_score
    reasons.append(f"energy proximity — ENERGY-FIRST mode (+{energy_score})")

    return round(score, 3), reasons


def recommend_songs_mode(
    user_prefs: dict,
    songs: list[dict],
    k: int = 5,
    mode: str = "default"
) -> list[dict]:
    """
    Recommend songs using a selectable scoring mode.

    mode options: 'default' | 'genre_first' | 'energy_first'
    """
    scorer_map = {
        "default":      score_song,
        "genre_first":  score_song_genre_first,
        "energy_first": score_song_energy_first,
    }
    scorer = scorer_map.get(mode, score_song)

    scored = []
    for song in songs:
        score, reasons = scorer(user_prefs, song)
        entry = dict(song)
        entry["score"] = score
        entry["reasons"] = reasons
        scored.append(entry)

    return sorted(scored, key=lambda s: s["score"], reverse=True)[:k]
