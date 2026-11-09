#!/usr/bin/env bash
# Read-only GET against *.roblox.com with the rustudio keyring session.
# The cookie only ever travels through curl's config on stdin; it is never an
# argument, an env var of a child, or printed.
#
# usage: tools/tc/rget.sh URL [extra curl args...]
# prints: HTTP status, then the body (first 4000 bytes)
set -euo pipefail
url=$1; shift
case "$url" in https://*.roblox.com/*) ;; *) echo "refusing non-roblox url" >&2; exit 2;; esac
c=$(secret-tool lookup service rustudio key roblox-cookie | tr -d '\r\n')
printf 'header = "Cookie: .ROBLOSECURITY=%s"\n' "$c" | \
  curl -s -K - -A 'Mozilla/5.0 (X11; Linux x86_64) rustudio-research' \
       -w '\nHTTP %{http_code}\n' "$@" "$url" | head -c 4000
unset c
echo
