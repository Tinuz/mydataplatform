# Kong met Database Mode (Optioneel)

Deze gids legt uit hoe je Kong kunt draaien met een database backend, zodat je Kong dynamisch kunt beheren via Konga of de Admin API.

## Waarom database mode?

### DB-less mode (huidige setup)
- ✅ Eenvoudig, geen extra database
- ✅ Snel opstarten
- ✅ Infrastructure as Code (YAML config)
- ❌ Kan niet via Admin API/Konga worden aangepast
- ❌ Requires restart voor wijzigingen

### Database mode
- ✅ Dynamische configuratie via API/Konga
- ✅ Geen restarts nodig voor wijzigingen
- ✅ Geschikt voor grote teams
- ❌ Extra database nodig
- ❌ Complexere setup

## Implementatie

### Optie A: Gebruik de hoofd-postgres (eenvoudig)

Voeg een database toe aan de bestaande postgres container:

#### 1. Update postgres-init/03_init_kong.sql

```sql
-- Kong database
CREATE DATABASE kong;
CREATE USER kong WITH PASSWORD 'kong';
GRANT ALL PRIVILEGES ON DATABASE kong TO kong;

-- Geef kong user alle rechten op de database
\c kong;
GRANT ALL ON SCHEMA public TO kong;
```

#### 2. Update docker-compose.yml

Vervang de Kong service met:

```yaml
  kong-migrations:
    image: kong:3.6
    container_name: dp_kong_migrations
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_PORT: 5432
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
    command: kong migrations bootstrap
    profiles: [ "standard" ]
    restart: on-failure

  kong:
    image: kong:3.6
    container_name: dp_kong
    depends_on:
      kong-migrations:
        condition: service_completed_successfully
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres
      KONG_PG_PORT: 5432
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_LOG_LEVEL: notice
      KONG_REAL_IP_HEADER: "X-Forwarded-For"
      KONG_REAL_IP_RECURSIVE: "on"
    ports:
      - "8000:8000"
      - "8001:8001"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512m
    profiles: [ "standard" ]
```

### Optie B: Aparte postgres voor Kong (geïsoleerd)

Voor een volledig geïsoleerde setup:

```yaml
  postgres_kong:
    image: postgres:13-alpine
    container_name: dp_postgres_kong
    environment:
      POSTGRES_USER: kong
      POSTGRES_PASSWORD: kong
      POSTGRES_DB: kong
    volumes:
      - kong_pgdata:/var/lib/postgresql/data
    ports:
      - "5434:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kong -d kong || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 10
    deploy:
      resources:
        limits:
          memory: 512m
    profiles: [ "standard" ]

  kong-migrations:
    image: kong:3.6
    container_name: dp_kong_migrations
    depends_on:
      postgres_kong:
        condition: service_healthy
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres_kong
      KONG_PG_PORT: 5432
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
    command: kong migrations bootstrap
    profiles: [ "standard" ]
    restart: on-failure

  kong:
    image: kong:3.6
    container_name: dp_kong
    depends_on:
      kong-migrations:
        condition: service_completed_successfully
    environment:
      KONG_DATABASE: postgres
      KONG_PG_HOST: postgres_kong
      KONG_PG_PORT: 5432
      KONG_PG_DATABASE: kong
      KONG_PG_USER: kong
      KONG_PG_PASSWORD: kong
      KONG_PROXY_LISTEN: "0.0.0.0:8000"
      KONG_ADMIN_LISTEN: "0.0.0.0:8001"
      KONG_LOG_LEVEL: notice
      KONG_REAL_IP_HEADER: "X-Forwarded-For"
      KONG_REAL_IP_RECURSIVE: "on"
    ports:
      - "8000:8000"
      - "8001:8001"
    healthcheck:
      test: ["CMD", "kong", "health"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512m
    profiles: [ "standard" ]

volumes:
  kong_pgdata:  # Voeg toe aan volumes sectie
```

## Migratie van DB-less naar Database mode

Als je wilt overstappen van de huidige DB-less setup naar database mode:

### 1. Exporteer huidige config (optioneel)

```bash
# Als je bestaande routes/services in kong.yml hebt:
cp kong/kong.yml kong/kong.yml.backup
```

### 2. Stop Kong

```bash
docker-compose down kong
```

### 3. Implementeer database mode

Kies Optie A of B hierboven en pas docker-compose.yml aan.

### 4. Start met migrations

```bash
# Optie A (hoofd postgres):
# Voeg eerst 03_init_kong.sql toe aan postgres-init/
docker-compose down postgres
docker volume rm data-platform_pgdata
docker-compose --profile standard up -d postgres

# Wacht tot postgres healthy is, dan:
docker-compose --profile standard up -d kong-migrations kong
```

### 5. Importeer oude config (optioneel)

Als je oude services/routes had in kong.yml, kun je deze via Konga of Admin API toevoegen:

```bash
# Via Admin API (voorbeeld voor een service):
curl -X POST http://localhost:8001/services \
  --data "name=my-service" \
  --data "url=http://example.com"

# Of gebruik Konga UI op http://localhost:1337
```

## Konga met database mode Kong

Met Kong in database mode werkt Konga naadloos:

1. Open Konga: http://localhost:1337
2. Voeg Kong connectie toe met `http://kong:8001`
3. Je kunt nu:
   - Services toevoegen/wijzigen
   - Routes configureren
   - Plugins beheren
   - Consumers aanmaken
   - En meer...

Alle wijzigingen zijn direct actief, geen restart nodig!

## Best practices

### Development
- **DB-less mode** is prima voor development
- Snel en eenvoudig
- Config in version control

### Staging/Production
- **Database mode** is aan te raden
- Betere schaalbaarheid
- Team collaboration via Konga
- Audit logging van wijzigingen

## Vergelijking

| Feature | DB-less | Database |
|---------|---------|----------|
| Setup complexity | Laag | Middel |
| Startup tijd | Snel | Langzamer |
| Dynamic config | ❌ | ✅ |
| Konga support | Readonly | Full |
| Restarts needed | Ja | Nee |
| Schaalbaarheid | Goed | Zeer goed |
| Config backup | YAML file | DB dump |

## Rollback

Als database mode niet werkt, terug naar DB-less:

```bash
# Stop services
docker-compose down kong kong-migrations

# Restore docker-compose.yml backup
git checkout docker-compose.yml

# Start Kong DB-less
docker-compose --profile standard up -d kong
```
