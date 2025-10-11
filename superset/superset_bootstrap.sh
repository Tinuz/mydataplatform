#!/usr/bin/env bash
set -e

# wacht even tot DB ready is (extra safety)
sleep 5

# init superset met DB
superset fab create-admin \
   --username admin \
   --firstname Admin \
   --lastname User \
   --email admin@local \
   --password admin

superset db upgrade
superset init

# (optioneel) kun je hier default databases toevoegen via CLI of post-start API calls
echo "Superset bootstrap complete."
