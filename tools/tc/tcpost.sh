#!/usr/bin/env bash
# The two harmless team-create-service POSTs (collaboration/hasTenure and
# collaboration/join), with the CSRF dance. Nothing else is allowed: every
# other Team Create POST changes state or is unverified.
#
# usage: tools/tc/tcpost.sh hasTenure|join UNIVERSE_ID
set -euo pipefail
case "$1" in hasTenure|join) ;; *) echo "only hasTenure or join" >&2; exit 2;; esac
url="https://apis.roblox.com/team-create-service/v1/collaboration/$1"
body=$(printf '{"universeId": %d}' "$2")
c=$(secret-tool lookup service rustudio key roblox-cookie | tr -d '\r\n')
call() {
  printf 'header = "Cookie: .ROBLOSECURITY=%s"\n%s' "$c" "${1:-}" | \
    curl -s -K - -D - -X POST -H 'Content-Type: application/json' \
         -A 'Mozilla/5.0 (X11; Linux x86_64) rustudio-research' --data "$body" "$url"
}
tok=$(call | tr -d '\r' | awk -F': ' 'tolower($1)=="x-csrf-token"{print $2}')
call "header = \"X-CSRF-TOKEN: $tok\"" | tr -d '\r' | awk 'NR==1 || body {print} /^$/ {body=1}'
unset c
echo
