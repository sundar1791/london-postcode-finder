import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(override=True)


@lru_cache(maxsize=1)
def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not key:
        raise ValueError("SUPABASE_KEY environment variable is not set")
    try:
        return create_client(url, key)
    except Exception as exc:
        raise RuntimeError(f"Could not connect to Supabase: {exc}") from exc
