#!/bin/bash
# Search plugins using pre-cached marketplace data from Step 2
# Uses separate .marketplace-*.json cache files if available, falls back to live fetch

SEARCH_TERM="${1:?Search term required}"
CACHE_DIR="${2:-.}"

TERM_LOWER=$(echo "$SEARCH_TERM" | tr '[:upper:]' '[:lower:]')

MARKETPLACE_REPOS=(
  "anthropics/claude-plugins-official"
  "anthropics/skills"
  "anthropics/knowledge-work-plugins"
  "anthropics/financial-services-plugins"
  "anthropics/claude-plugins-community"
)

search_marketplace() {
  local marketplace_data="$1"
  local search_term="$2"

  jq --arg term "$search_term" \
    '{marketplace_name: .name, plugins: [.plugins[] |
      select(
        (.name | ascii_downcase | contains($term)) or
        (.description // "" | ascii_downcase | contains($term))
      ) |
      {name, description: (.description // "")[0:60]}
    ]} |
    select(.plugins | length > 0)' \
    <<< "$marketplace_data" 2>/dev/null
}

# Main execution
echo "Searching across all 5 marketplaces for: '$SEARCH_TERM'"
echo "════════════════════════════════════════════════════════════"
echo ""

total_results=0

# Search each marketplace
for repo in "${MARKETPLACE_REPOS[@]}"; do
  reponame="${repo##*/}"
  cache_file="$CACHE_DIR/.marketplace-${reponame}.json"
  owner="${repo%%/*}"

  # Try to use cache first
  if [ -f "$cache_file" ]; then
    marketplace_data=$(cat "$cache_file")
  else
    # Fall back to live fetch
    marketplace_data=$(curl -s "https://raw.githubusercontent.com/$owner/$reponame/main/.claude-plugin/marketplace.json" 2>/dev/null)
  fi

  if [ -z "$marketplace_data" ]; then
    continue
  fi

  # Search this marketplace
  result=$(search_marketplace "$marketplace_data" "$TERM_LOWER")

  if [ -n "$result" ]; then
    marketplace_name=$(echo "$result" | jq -r '.marketplace_name' 2>/dev/null)
    count=$(echo "$result" | jq '.plugins | length' 2>/dev/null)
    echo "$marketplace_name ($count results):"
    echo "$result" | jq -r '.plugins[] | "  • \(.name) — \(.description)"' 2>/dev/null
    echo ""
    total_results=$((total_results + count))
  fi
done

echo "════════════════════════════════════════════════════════════"
echo "Total results: $total_results"
