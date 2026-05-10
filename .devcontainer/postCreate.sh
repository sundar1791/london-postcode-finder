#!/bin/bash
set -e

pip install -r requirements.txt
pip install supabase --break-system-packages 2>/dev/null || true

cat > .env <<EOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
TFL_APP_KEY=${TFL_APP_KEY:-}
SUPABASE_URL=${SUPABASE_URL:-}
SUPABASE_KEY=${SUPABASE_KEY:-}
GROQ_API_KEY=${GROQ_API_KEY:-}
EOF

echo "Codespaces environment ready"
