#!/usr/bin/env bash

# dbt Investigations Setup Script
# This script sets up the dbt project for canonical data models

set -e  # Exit on error

echo "🚀 Setting up dbt Investigations project..."

# Check if we're in the right directory
if [ ! -f "dbt_project.yml" ]; then
    echo "❌ Error: dbt_project.yml not found. Please run from dbt_investigations/ directory"
    exit 1
fi

# 1. Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install dbt-postgres>=1.7.0 great-expectations>=0.18.0 dagster-dbt

# 2. Install dbt packages
echo ""
echo "📚 Installing dbt packages (dbt_expectations, dbt_utils)..."
dbt deps

# 3. Debug dbt setup
echo ""
echo "🔍 Running dbt debug to verify configuration..."
dbt debug

# 4. Create schemas in PostgreSQL
echo ""
echo "🏗️  Creating schemas in PostgreSQL..."
echo "NOTE: Make sure PostgreSQL is running and accessible"
echo "Schemas will be created on first dbt run"

# 6. Run dbt to build canonical models
echo ""
echo "⚙️  Building canonical models..."
dbt build --select canonical

# 7. Generate documentation
echo ""
echo "📖 Generating dbt documentation..."
dbt docs generate

# 8. Test data quality
echo ""
echo "🧪 Running data quality tests..."
dbt test --select canonical

# 9. Initialize Great Expectations (optional)
echo ""
read -p "❓ Do you want to initialize Great Expectations? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🎯 Initializing Great Expectations..."
    great_expectations init
    echo "✅ Great Expectations initialized. See GREAT_EXPECTATIONS.md for usage."
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. View documentation: dbt docs serve"
echo "   2. Run models: dbt run --select canonical"
echo "   3. Test quality: dbt test --select canonical"
echo "   4. Full build: dbt build --select canonical"
echo ""
echo "🔧 Useful commands:"
echo "   dbt compile           # Compile SQL without running"
echo "   dbt run --full-refresh  # Force rebuild all tables"
echo "   dbt test --store-failures  # Store failed test results"
echo "   dbt source freshness  # Check source data freshness"
echo ""
echo "📚 Documentation:"
echo "   README.md              # Project overview"
echo "   GREAT_EXPECTATIONS.md  # Data quality setup"
echo "   models/canonical/schema.yml  # Data contracts"
echo ""
