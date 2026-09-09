#!/usr/bin/env bash
#
# Walk the fetcher up a ladder of chunk ceilings.
#
# Each rung takes every unfinished book as deep as that ceiling, then stops.
# Climbing gets the shallow books done early instead of spending a whole night
# on one 900-chunk mahabharata, and the journal makes each rung resumable --
# a book stopped at 150 restarts at 151, refetching nothing.
#
# **A rung must be allowed to finish.** `|| break` below is load-bearing: if a
# rung exits non-zero it was cut short, and stepping to the next ceiling would
# walk past every book it had not reached yet. That is not hypothetical --
# before 2026-08-19 `fetch_text` gave up after 3 clearance lapses and exited 0,
# so four rungs ran overnight while 431 books sat untouched at cursor 50.
#
# Usage:
#   ./run_ladder.sh                  # the default ladder, 50..1500
#   ./run_ladder.sh 50 100 200       # just these rungs
#   MAX_REQUESTS=500 ./run_ladder.sh # pass a budget through to each rung
#
# REPAIRING SPECIFIC BOOKS:
#   SERIALS=398,634,1199 PATIENCE=15 ./run_ladder.sh 150 300 600
#
# `SERIALS` restricts every rung to those books and overrides the journal's
# `complete` flag -- which is the point, since a book wrongly ended by too
# short a patience is marked complete and no ordinary rung would revisit it.
# `PATIENCE` raises how many consecutive dead chunks are tolerated before a
# book is believed finished. The default was 3 until 2026-09-06, when fourteen
# books it had stopped inside their front matter were rerun at 50 and gave up
# 23.3 MB between them; the default is now 50, so `PATIENCE` is for going
# higher still on a book that looks truncated even after that.
#
# Give a repair its own short ladder. The default runs to 2000 and every rung
# re-walks nothing, but a rung still costs one request per book to discover it
# is done, and forty rungs over three books is 120 wasted requests.
#
# NOT `set -u`: macOS ships bash 3.2, where expanding an empty array as
# "${arr[@]}" is an unbound-variable error, which would kill this script on its
# first rung whenever MAX_REQUESTS is unset.
set -o pipefail

cd "$(dirname "$0")"

if [ $# -gt 0 ]; then
  RUNGS=("$@")
else
  RUNGS=(50 100 150 200 250 300 350 400 450 500 550 600 650 700 750 800 850 900 950 1000 1050 1100 1150 1200 1250 1300 1350 1400 1450 1500 1550 1600 1650 1700 1750 1800 1850 1900 1950 2000)
fi

MAX_REQUESTS="${MAX_REQUESTS:-}"
SERIALS="${SERIALS:-}"
PATIENCE="${PATIENCE:-}"

# Built once rather than inside the loop: bash 3.2 has no nameref, and
# rebuilding per rung invites one rung disagreeing with the next about which
# books it is even walking.
EXTRA=()
[ -n "$SERIALS" ]  && EXTRA+=(--serials "$SERIALS")
[ -n "$PATIENCE" ] && EXTRA+=(--patience "$PATIENCE")

if [ -n "$SERIALS" ]; then
  echo "repairing serials: $SERIALS${PATIENCE:+ (patience $PATIENCE)}"
fi

started=$(date '+%s')
for c in "${RUNGS[@]}"; do
  echo
  echo "=== ceiling $c — $(date '+%F %T') ==="

  # "${EXTRA[@]}" is safe unquoted-empty here only because `set -u` is off --
  # see the note above; on bash 3.2 an empty array expansion would otherwise
  # abort the first rung.
  if [ -n "$MAX_REQUESTS" ]; then
    python -m pipeline.fulltext --max-chunks "$c" --max-requests "$MAX_REQUESTS" "${EXTRA[@]}"
  else
    python -m pipeline.fulltext --max-chunks "$c" "${EXTRA[@]}"
  fi
  status=$?

  if [ $status -ne 0 ]; then
    echo
    echo "!!! ceiling $c exited $status — stopping the ladder here."
    echo "    The rung is UNFINISHED. Everything fetched is on disk; rerun"
    echo "    this same ceiling to continue:"
    echo "        python -m pipeline.fulltext --max-chunks $c ${EXTRA[*]}"
    exit $status
  fi
done

echo
echo "=== ladder complete — $(date '+%F %T'), $((($(date '+%s') - started) / 60))m ==="
