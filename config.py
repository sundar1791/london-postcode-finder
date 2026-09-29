from dotenv import load_dotenv
import os

load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TFL_APP_KEY = os.getenv("TFL_APP_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Models and token budgets
SONNET_MODEL = os.getenv("SONNET_MODEL", "claude-sonnet-5")
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")
ORCHESTRATOR_MAX_TOKENS = int(os.getenv("ORCHESTRATOR_MAX_TOKENS", "1500"))
SYNTHESISER_MAX_TOKENS = int(os.getenv("SYNTHESISER_MAX_TOKENS", "8000"))
RESEARCH_MAX_TOKENS = int(os.getenv("RESEARCH_MAX_TOKENS", "500"))
WEB_SEARCH_MAX_TOKENS = int(os.getenv("WEB_SEARCH_MAX_TOKENS", "2000"))
DISTILLER_MAX_TOKENS = int(os.getenv("DISTILLER_MAX_TOKENS", "8000"))

# Pipeline behaviour
RESEARCH_CONCURRENCY = int(os.getenv("RESEARCH_CONCURRENCY", "5"))
DISTILL_EVERY_N = int(os.getenv("DISTILL_EVERY_N", "10"))
PIPELINE_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_TIMEOUT_SECONDS", "240"))
SPAWN_TIMEOUT_SECONDS = int(os.getenv("SPAWN_TIMEOUT_SECONDS", "90"))
SPAWN_CACHE_MAX_AGE_DAYS = int(os.getenv("SPAWN_CACHE_MAX_AGE_DAYS", "30"))

# API protection
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "5"))
DAILY_SEARCH_CAP = int(os.getenv("DAILY_SEARCH_CAP", "100"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CRON_SECRET = os.getenv("CRON_SECRET", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "")

OVERPASS_USER_AGENT = "london-postcode-finder/1.0 (portfolio project)"

# 40 postcode districts covering inner and outer London across all compass
# directions and zones. Mix of central (Z1), inner (Z2-3), outer (Z3-6).
LONDON_POSTCODE_DISTRICTS = [
    # Central – Zone 1
    "EC1A", "WC1A", "SW1A", "W1A",
    # Inner North
    "N1", "N4", "NW1", "NW3",
    # Inner East
    "E1", "E2",
    # Inner South-East
    "SE1", "SE5",
    # Inner South-West
    "SW4", "SW8",
    # Inner West
    "W2", "W6",
    # Inner North-West
    "NW6",
    # Outer North
    "N13", "N21", "EN1",
    # Outer North-East
    "E11", "E17", "IG1",
    # Outer East
    "RM1",
    # Outer South-East
    "SE9", "SE18", "DA1", "BR1", "BR3",
    # Outer South
    "CR0", "SM1",
    # Outer South-West
    "SW16", "SW19", "KT1", "TW1",
    # Outer West
    "W5", "W13", "UB1",
    # Outer North-West
    "NW9", "HA1",
]

SCORING_DIMENSIONS = {
    "safety": "Safety",
    "green_space": "Green Space",
    "nightlife": "Nightlife",
    "transport": "Transport",
    "rent": "Rent",
}
