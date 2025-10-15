#!/bin/bash
# Serve dbt docs for data stewards
# Access at: http://localhost:8011

set -e

echo "🔧 Generating dbt documentation..."
dbt docs generate

echo "📚 Starting documentation server..."
echo "✨ Documentation available at: http://localhost:8011"
echo "Press Ctrl+C to stop"

dbt docs serve --port 8011 --host 0.0.0.0
