"""
evaluator.py — Reliability evaluation layer for VibeFinder 2.0.

This module scores the *quality* of a recommendation set against the user's
stated preferences. The score is combined with the AI's own extraction
confidence to produce the final reliability indicator shown to the user.
"""


# ── Quality scoring ────────────────────────────────────────────────────────────

def evaluate_recommendations(user_prefs: dict, recs: list[dict]) -> dict:
    """
    Evaluate a recommendation set and return a reliability summary.

    Checks:
      1. Genre match rate  — what fraction of top-5 match the target genre
      2. Mood match rate   — what fraction of top-5 match the target mood
      3. Average score     — mean recommendation score (normalized to 0–1 scale,
                             max possible score is 7.0)
      4. Top-1 score       — confidence in the single best result

    Returns:
        {
          "quality_score": float (0.0–1.0),
          "genre_match_rate": float,
          "mood_match_rate": float,
          "avg_score_normalized": float,
          "summary": str
        }
    """
    if not recs:
        return {
            "quality_score": 0.0,
            "genre_match_rate": 0.0,
            "mood_match_rate": 0.0,
            "avg_score_normalized": 0.0,
            "summary": "No recommendations to evaluate.",
        }

    target_genre = user_prefs.get("favorite_genre", "").lower()
    target_mood  = user_prefs.get("favorite_mood", "").lower()
    MAX_SCORE    = 7.0   # theoretical max from scoring algorithm

    genre_matches = sum(1 for r in recs if r["genre"] == target_genre)
    mood_matches  = sum(1 for r in recs if r["mood"]  == target_mood)
    genre_rate    = round(genre_matches / len(recs), 3)
    mood_rate     = round(mood_matches  / len(recs), 3)

    avg_score = sum(r["score"] for r in recs) / len(recs)
    avg_norm  = round(min(avg_score / MAX_SCORE, 1.0), 3)

    top1_norm = round(min(recs[0]["score"] / MAX_SCORE, 1.0), 3)

    # Weighted composite: genre match counts most, then mood, then score quality
    quality_score = round(
        0.40 * genre_rate +
        0.30 * mood_rate  +
        0.20 * avg_norm   +
        0.10 * top1_norm,
        3
    )

    summary = (
        f"Genre match {genre_matches}/{len(recs)} | "
        f"Mood match {mood_matches}/{len(recs)} | "
        f"Avg score {avg_score:.2f}/{MAX_SCORE:.1f} | "
        f"Quality {quality_score:.0%}"
    )

    return {
        "quality_score": quality_score,
        "genre_match_rate": genre_rate,
        "mood_match_rate": mood_rate,
        "avg_score_normalized": avg_norm,
        "summary": summary,
    }


# ── Display helper ─────────────────────────────────────────────────────────────

def confidence_bar(score: float, width: int = 20) -> str:
    """Return an ASCII confidence bar with emoji indicator."""
    filled = int(score * width)
    bar    = "█" * filled + "░" * (width - filled)
    if score >= 0.75:
        label = "🟢"
    elif score >= 0.60:
        label = "🟡"
    else:
        label = "🔴"
    return f"{label} [{bar}] {score:.0%}"
