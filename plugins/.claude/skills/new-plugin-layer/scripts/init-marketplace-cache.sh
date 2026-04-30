#!/bin/bash
# Step 2: Fetch and cache all marketplace plugin metadata
# Builds separate cache files for each marketplace to avoid size limits

CACHE_DIR="${PLUGIN_CACHE_DIR:-.}"
mkdir -p "$CACHE_DIR"

MARKETPLACE_REPOS=(
  "anthropics/claude-plugins-official"
  "anthropics/skills"
  "anthropics/knowledge-work-plugins"
  "anthropics/financial-services-plugins"
  "anthropics/claude-plugins-community"
)

echo "Initializing marketplace cache..." >&2

total_plugins=0

# Fetch each marketplace into separate cache file
for repo in "${MARKETPLACE_REPOS[@]}"; do
  reponame="${repo##*/}"
  owner="${repo%%/*}"
  cache_file="$CACHE_DIR/.marketplace-${reponame}.json"

  echo "  Fetching $reponame..." >&2

  # Fetch marketplace.json directly
  curl -s "https://raw.githubusercontent.com/$owner/$reponame/main/.claude-plugin/marketplace.json" \
    -o "$cache_file.tmp" 2>/dev/null

  if [ ! -s "$cache_file.tmp" ]; then
    echo "  WARNING: Failed to fetch $repo" >&2
    rm -f "$cache_file.tmp"
    continue
  fi

  # Validate JSON and get plugin count
  plugin_count=$(jq '.plugins | length' "$cache_file.tmp" 2>/dev/null || echo 0)
  marketplace_name=$(jq -r '.name // ""' "$cache_file.tmp" 2>/dev/null || echo "$reponame")

  if [ "$plugin_count" -gt 0 ]; then
    mv "$cache_file.tmp" "$cache_file"
    echo "    Cached $plugin_count plugins ($marketplace_name)" >&2
    total_plugins=$((total_plugins + plugin_count))
  else
    echo "    WARNING: Invalid or empty marketplace.json" >&2
    rm -f "$cache_file.tmp"
  fi
done

# Create index file pointing to all caches
echo '{"marketplaces": [
  "anthropics/claude-plugins-official",
  "anthropics/skills",
  "anthropics/knowledge-work-plugins",
  "anthropics/financial-services-plugins",
  "anthropics/claude-plugins-community"
], "cache_dir": "'$CACHE_DIR'", "plugin_count": '$total_plugins', "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$CACHE_DIR/.marketplace-index.json"

echo "Cache initialized: $total_plugins total plugins" >&2
echo "$CACHE_DIR"
