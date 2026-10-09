#!/bin/bash
# EUCLID-CORE / PYTHIA — Docker cleanup script
# Reclaims disk space by removing old builds, images, and containers.
# Run this before deploying to ensure you have the full 100GB available.

set -e

echo "=== Docker Disk Usage (before) ==="
docker system df 2>/dev/null || echo "(Docker not responding)"

echo ""
echo "=== Removing stopped containers ==="
docker container prune -f 2>/dev/null || true

echo ""
echo "=== Removing dangling images ==="
docker image prune -f 2>/dev/null || true

echo ""
echo "=== Removing unused images (untagged) ==="
docker image prune -a -f --filter "until=48h" 2>/dev/null || true

echo ""
echo "=== Removing unused volumes ==="
docker volume prune -f 2>/dev/null || true

echo ""
echo "=== Removing build cache ==="
docker builder prune -f 2>/dev/null || true

echo ""
echo "=== Docker Disk Usage (after) ==="
docker system df 2>/dev/null || echo "(Docker not responding)"

echo ""
echo "=== Done. You should now have close to the full 100GB available. ==="
echo "To deploy: docker compose up -d --build"
