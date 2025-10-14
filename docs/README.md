# 📚 Data Platform Documentation

**Welcome!** This is your complete guide to the data platform.

---

## 🚀 Getting Started (Start Here!)

New to the platform? Start with these essential guides:

1. **[Quick Reference](QUICK_REFERENCE.md)** ⚡
   - Essential commands & workflows
   - Copy-paste ready commands
   - Common troubleshooting

2. **[Data Engineer Onboarding](DATA_ENGINEER_ONBOARDING.md)** 👨‍💻
   - Complete onboarding guide
   - Architecture overview
   - Step-by-step tutorials

3. **[Platform Status](PLATFORM_STATUS.md)** 📊
   - Current capabilities
   - Available datasets
   - Service status

---

## 🔧 Core Components

### 💰 Crypto Streaming Pipeline

- **[Crypto Stream Architecture](CRYPTO_STREAM_ARCHITECTURE.md)**
  - System design & data flow
  - Technologies: Kafka, Iceberg, DuckDB, Dagster
  - Bronze/Silver layer architecture

- **[Crypto Stream Quickstart](CRYPTO_STREAM_QUICKSTART.md)**
  - Getting started guide
  - Materialize assets
  - Query examples

### 🎨 Visualization & Analytics (Superset)

- **[Superset Problem Solved](SUPERSET_PROBLEM_SOLVED.md)** ⭐ **START HERE**
  - Latest solution for DuckDB multi-statement issue
  - PostgreSQL sync workaround
  - Ready-to-use queries
  - Chart creation guide

- **[Superset Database Connections](SUPERSET_DATABASE_CONNECTIONS.md)**
  - PostgreSQL connection
  - DuckDB connection (backend only)
  - SQLAlchemy URIs

- **[Superset Quick Reference](SUPERSET_QUICK_REFERENCE.md)**
  - Copy-paste connection strings
  - Top 5 queries
  - Emergency commands

- **[Superset Dashboards](SUPERSET_DASHBOARDS.md)**
  - Dashboard examples
  - Chart types

### 🔄 Orchestration (Dagster)

- **[Orchestration Complete](ORCHESTRATION_COMPLETE.md)**
  - Dagster implementation status
  - Asset definitions
  - Materialization guide

- **[Dagster gRPC Fix](DAGSTER_GRPC_FIX.md)** 🐛
  - Troubleshooting gRPC errors
  - Port configuration
  - Health checks

### 📈 Data Lineage & Governance

- **[Marquez Integration](MARQUEZ_INTEGRATION.md)**
  - Data lineage tracking
  - OpenLineage integration
  - Viewing lineage graphs

- **[Data Catalog](DATA_CATALOG.md)**
  - Amundsen setup
  - Metadata management
  - Search & discovery

### 🌤️ Weather API (Bonus Feature)

- **[Weather API](WEATHER_API.md)**
  - RESTful API reference
  - Endpoints & parameters
  - Sample queries

- **[Weather API Implementation](WEATHER_API_IMPLEMENTATION.md)**
  - Technical implementation details
  - Database schema
  - Materialized views

---

## 🐛 Troubleshooting

### Common Issues

1. **Dagster gRPC Errors**: See [DAGSTER_GRPC_FIX.md](DAGSTER_GRPC_FIX.md)
2. **Superset Connection Issues**: See [SUPERSET_PROBLEM_SOLVED.md](SUPERSET_PROBLEM_SOLVED.md)
3. **Service Won't Start**: Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) troubleshooting section

### Quick Commands

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f <service>

# Restart service
docker-compose restart <service>

# Re-initialize platform
./scripts/bootstrap.sh
```

---

## 📖 Document Categories

### By Topic
- **Getting Started**: Quick Reference, Onboarding, Platform Status
- **Streaming**: Crypto Stream Architecture, Crypto Stream Quickstart
- **Visualization**: Superset (3 docs)
- **Orchestration**: Dagster (2 docs)
- **Governance**: Marquez, Data Catalog
- **APIs**: Weather API (2 docs)

### By Role
- **New Engineers**: Onboarding → Quick Reference → Platform Status
- **Data Engineers**: Crypto Stream Architecture → Orchestration Complete
- **Analysts**: Superset Problem Solved → Superset Quick Reference
- **DevOps**: Quick Reference → Dagster gRPC Fix

---

## 📝 Contributing to Documentation

### Adding New Documentation

1. Create markdown file in `docs/`
2. Add to this index (README.md)
3. Link from main README if essential
4. Use clear titles and structure

### Documentation Standards

- **Use emojis** for visual hierarchy (📊 🔧 ⚡ 🐛)
- **Include code examples** with syntax highlighting
- **Add links** to related docs
- **Keep it current** - update when features change

---

## 🗂️ All Documents (Alphabetical)

| Document | Lines | Category | Updated |
|----------|-------|----------|---------|
| [Crypto Stream Architecture](CRYPTO_STREAM_ARCHITECTURE.md) | 371 | Streaming | Current |
| [Crypto Stream Quickstart](CRYPTO_STREAM_QUICKSTART.md) | 251 | Streaming | Current |
| [Dagster gRPC Fix](DAGSTER_GRPC_FIX.md) | 171 | Troubleshooting | Current |
| [Data Catalog](DATA_CATALOG.md) | 539 | Governance | Current |
| [Data Engineer Onboarding](DATA_ENGINEER_ONBOARDING.md) | 1,332 | Getting Started | Current |
| [Marquez Integration](MARQUEZ_INTEGRATION.md) | 341 | Governance | Current |
| [Orchestration Complete](ORCHESTRATION_COMPLETE.md) | 366 | Orchestration | Current |
| [Platform Status](PLATFORM_STATUS.md) | 267 | Getting Started | Current |
| [Quick Reference](QUICK_REFERENCE.md) | 491 | Getting Started | Current |
| [Superset Dashboards](SUPERSET_DASHBOARDS.md) | 258 | Visualization | Current |
| [Superset Database Connections](SUPERSET_DATABASE_CONNECTIONS.md) | 375 | Visualization | Current |
| [Superset Problem Solved](SUPERSET_PROBLEM_SOLVED.md) | 205 | Visualization | Current ⭐ |
| [Superset Quick Reference](SUPERSET_QUICK_REFERENCE.md) | 125 | Visualization | Current |
| [Weather API](WEATHER_API.md) | 320 | APIs | Current |
| [Weather API Implementation](WEATHER_API_IMPLEMENTATION.md) | 232 | APIs | Current |

**Total**: 15 documents, ~5,644 lines (30% reduction from original 21 docs)

---

## 🎯 Documentation Status

✅ **Completed Cleanup** (Oct 12, 2025):
- Removed 5 redundant Superset docs
- Removed 2 outdated planning docs
- Created this index for easy navigation
- Reduced total documentation by 30%

---

## 💡 Next Steps

1. Read the [Quick Reference](QUICK_REFERENCE.md) for essential commands
2. Complete the [Data Engineer Onboarding](DATA_ENGINEER_ONBOARDING.md)
3. Explore specific components as needed
4. Check [Platform Status](PLATFORM_STATUS.md) for current capabilities

**Questions?** All guides include troubleshooting sections!
