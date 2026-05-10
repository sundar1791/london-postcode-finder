import sys
import os
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scorers.crime_scorer import score_all_from_cache as _crime_cache
from scorers.green_scorer import score_all_from_cache as _green_cache
from scorers.nightlife_scorer import score_all_from_cache as _nightlife_cache
from scorers.transport_scorer import score_all_from_cache as _transport_cache
from scorers.rent_scorer import score_all_from_cache as _rent_cache


def read_all_scores_from_cache(supabase=None) -> dict[str, dict[str, float]]:
    return {
        "crime": _crime_cache(supabase=supabase),
        "green": _green_cache(supabase=supabase),
        "nightlife": _nightlife_cache(supabase=supabase),
        "transport": _transport_cache(supabase=supabase),
        "rent": _rent_cache(supabase=supabase),
    }


if __name__ == "__main__":
    import json
    scores = read_all_scores_from_cache()
    for dimension, districts in scores.items():
        print(f"{dimension}: {len(districts)} districts loaded")
    print(json.dumps(scores, indent=2))
