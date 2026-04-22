"""
main.py — VibeFinder 2.0 entry point.

Extends VibeFinder 1.0 (Module 3) with:
  - Natural language input via Anthropic API
  - Confidence scoring on every recommendation set
  - Input guardrails
  - Session logging

Run with:
    python -m src.main
"""

import os
import sys
import logging
import datetime

import anthropic

from src.recommender import load_songs, recommend_songs, recommend_songs_mode
from src.evaluator import evaluate_recommendations, confidence_bar

# ── Logging ────────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/session_{datetime.date.today()}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Anthropic client ───────────────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-5"

SYSTEM_PROMPT = """You are VibeFinder AI, a music preference parser.

Your ONLY job is to extract music preferences from a user message and return them
as a JSON object — nothing else.

Required JSON format (all keys mandatory):
{
  "favorite_genre": "<one of: pop, rock, hiphop, rnb, lofi, electronic, country, latin, classical, metal>",
  "favorite_mood": "<one of: happy, calm, intense, romantic, sad, dark, melancholic, epic, angry, confident>",
  "target_energy": <float 0.0–1.0>,
  "target_valence": <float 0.0–1.0>,
  "target_danceability": <float 0.0–1.0>,
  "target_acousticness": <float 0.0–1.0>,
  "confidence": <float 0.0–1.0 — how confident you are in this extraction>
}

Rules:
- Return ONLY the JSON object. No markdown fences, no preamble, no explanation.
- If the user's request is vague, make reasonable inferences and lower the confidence score.
- If the message is not about music at all (spam, harmful content, gibberish), return:
  {"error": "not_music_related"}
- Never fabricate genres or moods outside the allowed lists.
"""


# ── Guardrails ─────────────────────────────────────────────────────────────────
BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "ignore your system prompt",
    "you are now",
    "forget everything",
    "jailbreak",
    "disregard",
]

def is_blocked(text: str) -> bool:
    lower = text.lower()
    for p in BLOCKED_PATTERNS:
        if p in lower:
            logger.warning("Guardrail triggered | input: %.80s", text)
            return True
    return False


# ── AI preference parser ───────────────────────────────────────────────────────
def parse_preferences(user_input: str) -> dict | None:
    """
    Send user_input to Claude and parse a structured preference dict.
    Returns None on API error. Returns {"error": "not_music_related"} if blocked by model.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_input}],
        )
        raw = response.content[0].text.strip()
        # Strip accidental markdown fences
        raw = raw.replace("```json", "").replace("```", "").strip()
        import json
        return json.loads(raw)
    except Exception as e:
        logger.error("parse_preferences error: %s", e)
        return None


# ── Display helpers ────────────────────────────────────────────────────────────
SEP = "─" * 62

def print_header(title: str) -> None:
    print(f"\n{'═' * 62}")
    print(f"  🎵  {title}")
    print(f"{'═' * 62}")

def print_recommendations(recs: list[dict], confidence: float) -> None:
    for rank, song in enumerate(recs, 1):
        print(f"\n  #{rank}  {song['title']}  —  {song['artist']}")
        print(f"       Genre: {song['genre'].title()} | Mood: {song['mood'].title()} | "
              f"Energy: {song['energy']}")
        print(f"       Score: {song['score']}")
        print(f"       Why:   {' | '.join(song['reasons'])}")
        print(f"       {SEP}")
    print(f"\n  Reliability: {confidence_bar(confidence)}")
    if confidence < 0.6:
        print("  ⚠️  Low confidence — try describing your mood in more detail.")


# ── Main REPL ──────────────────────────────────────────────────────────────────
def main() -> None:
    songs = load_songs()
    print(f"\n{'═' * 62}")
    print("  🎵  VibeFinder 2.0 — AI Music Recommender")
    print(f"  Loaded {len(songs)} songs")
    print("  Type 'quit' to exit | 'demo' for a quick demo")
    print(f"{'═' * 62}\n")

    while True:
        try:
            user_input = input("Describe your vibe: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye! 🎶")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye! 🎶")
            break
        if user_input.lower() == "demo":
            _run_demo(songs)
            continue

        # Guardrail check
        if is_blocked(user_input):
            print("\n⚠️  That input can't be processed. Please describe your music mood.\n")
            continue

        print("\n  🔍 Analyzing your vibe...")
        prefs = parse_preferences(user_input)

        if prefs is None:
            print("\n  ❌ Couldn't reach AI. Check your API key and connection.\n")
            continue

        if prefs.get("error") == "not_music_related":
            print("\n  🎵 Please describe what kind of music you're in the mood for!\n")
            continue

        ai_confidence = prefs.pop("confidence", 0.8)
        recs = recommend_songs(prefs, songs, k=5)
        eval_result = evaluate_recommendations(prefs, recs)

        # Combine AI extraction confidence + recommendation quality score
        combined_confidence = round((ai_confidence + eval_result["quality_score"]) / 2, 3)

        logger.info(
            "INPUT: %.80s | AI_CONF: %.2f | QUALITY: %.2f | COMBINED: %.2f",
            user_input, ai_confidence, eval_result["quality_score"], combined_confidence
        )

        print_header(f"Your VibeFinder picks — {prefs.get('favorite_genre','').title()} / "
                     f"{prefs.get('favorite_mood','').title()}")
        print_recommendations(recs, combined_confidence)
        print(f"\n  📊 Quality breakdown: {eval_result['summary']}\n")


def _run_demo(songs: list[dict]) -> None:
    """Run 3 preset demo inputs so the user can see the system end-to-end."""
    demos = [
        "I want something upbeat and danceable, pop music to get me hyped",
        "Something super chill to study to, acoustic and low energy",
        "Hard rock, intense, I need to feel pumped up for the gym",
    ]
    for desc in demos:
        print(f"\n  ▶ Demo input: \"{desc}\"")
        if is_blocked(desc):
            continue
        prefs = parse_preferences(desc)
        if not prefs or prefs.get("error"):
            print("  (skipped — parse error)")
            continue
        ai_conf = prefs.pop("confidence", 0.8)
        recs = recommend_songs(prefs, songs, k=3)
        eval_result = evaluate_recommendations(prefs, recs)
        combined = round((ai_conf + eval_result["quality_score"]) / 2, 3)
        print_header(f"{prefs.get('favorite_genre','').title()} / {prefs.get('favorite_mood','').title()}")
        print_recommendations(recs, combined)
        print(f"  📊 {eval_result['summary']}\n")


if __name__ == "__main__":
    main()
