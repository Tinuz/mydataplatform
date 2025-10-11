# Kong & Konga Setup

Deze directory bevat de configuratie voor Kong API Gateway en Konga (Kong Admin UI).

## ⚠️ Apple Silicon (M1/M2) Gebruikers

Als je een Mac met Apple Silicon hebt, gebruik dan het meegeleverde setup script:

```bash
cd kong
./setup-konga.sh
```

Dit script handelt automatisch de database initialisatie af. Zie [APPLE_SILICON_FIX.md](APPLE_SILICON_FIX.md) voor details.

## Overzicht

- **Kong**: API Gateway die draait in DB-less mode met declarative config
- **Konga**: Web UI voor het beheren van Kong
- **postgres_konga**: Aparte PostgreSQL database voor Konga's metadata

## Services

### Kong (API Gateway)
- **Proxy poort**: http://localhost:8000
- **Admin API**: http://localhost:8001
- **Mode**: DB-less (configuratie via `kong.yml`)

### Konga (Admin UI)
- **URL**: http://localhost:1337
- **Database**: Aparte PostgreSQL instance op poort 5433

## Eerste keer opstarten

### Snelle setup (Apple Silicon/M1/M2)

```bash
cd kong
./setup-konga.sh
```

Spring naar stap 3 voor Konga configuratie.

### Handmatige setup (alle platforms)

### 1. Start de services

```bash
docker-compose --profile standard up -d postgres_konga kong
```

**Let op (alleen Apple Silicon)**: Na deze stap moet je eenmalig de database initialiseren:

```bash
docker-compose run --rm konga -c prepare -a postgres \
  -u postgresql://konga:konga@postgres_konga:5432/konga
```

Dan pas Konga starten:

```bash
docker-compose up -d konga
```

### 2. Wacht tot alle services healthy zijn

```bash
docker-compose ps
```

Controleer of:
- ✅ postgres_konga: healthy
- ✅ kong: healthy  
- ✅ konga: up

### 3. Konga configureren (eerste keer)

1. Open http://localhost:1337
2. Maak een admin account aan:
   - Username: `admin`
   - Email: `admin@example.com`
   - Password: [kies een sterk wachtwoord]

3. Na login, voeg een Kong connectie toe:
   - **Name**: `Local Kong`
   - **Kong Admin URL**: `http://kong:8001`
   - Klik **Create Connection**

4. Activeer de connectie en je bent klaar!

## Kong configuratie

Kong draait in **DB-less mode**, wat betekent dat alle configuratie via het `kong.yml` bestand gaat.

### Huidige configuratie

Het bestand `kong/kong.yml` bevat:
- Services (upstream APIs)
- Routes (URL mappings)
- Plugins (rate limiting, auth, etc.)

### Configuratie wijzigen

1. Bewerk `kong/kong.yml`
2. Herstart Kong:
   ```bash
   docker-compose restart kong
   ```

**Let op**: In DB-less mode kun je Kong NIET via de Admin API of Konga wijzigen. Alle wijzigingen moeten via het YAML bestand.

## Alternatief: Kong met database

Als je Kong via Konga wilt beheren (dynamisch zonder restarts), moet je Kong in database mode draaien. Zie `docs/kong-with-db.md` voor instructies.

## Veelvoorkomende taken

### Kong logs bekijken
```bash
docker-compose logs -f kong
```

### Konga logs bekijken
```bash
docker-compose logs -f konga
```

### Kong configuratie valideren
```bash
docker-compose exec kong kong config parse /kong/declarative/kong.yml
```

### Konga database resetten
```bash
docker-compose down konga postgres_konga
docker volume rm data-platform_konga_data data-platform_konga_pgdata
docker-compose --profile standard up -d postgres_konga konga
```

### Kong Admin API testen
```bash
curl http://localhost:8001/status
curl http://localhost:8001/services
curl http://localhost:8001/routes
```

## Beveiliging

### Productie checklist

Voor productie gebruik, pas het volgende aan:

1. **Wijzig TOKEN_SECRET** in docker-compose.yml:
   ```bash
   # Genereer een sterke random string
   openssl rand -base64 32
   ```
   Update `TOKEN_SECRET` in de `konga` service.

2. **Verwijder exposed ports** (5433, 8001) als deze niet nodig zijn van buitenaf

3. **Gebruik Kong met database** + authenticatie plugin op de Admin API

4. **Enable HTTPS** voor Kong proxy en admin API

5. **Gebruik secrets management** (Docker secrets, Vault) ipv plaintext wachtwoorden

6. **Beperk CORS** in Konga settings

## Troubleshooting

### Konga kan geen verbinding maken met Kong

**Symptoom**: "Could not connect to Kong Admin" error

**Oplossing**:
1. Controleer of Kong healthy is: `docker-compose ps kong`
2. Test Kong Admin API: `curl http://localhost:8001/status`
3. In Konga, gebruik `http://kong:8001` (niet localhost!)

### Konga migration errors

**Symptoom**: Database migration errors bij start

**Oplossing**:
```bash
# Reset de database
docker-compose down konga
docker volume rm data-platform_konga_data
docker-compose up -d konga
```

### Kong configuratie wordt niet geladen

**Symptoom**: Services/routes verschijnen niet

**Oplossing**:
1. Valideer YAML syntax:
   ```bash
   docker-compose exec kong kong config parse /kong/declarative/kong.yml
   ```
2. Check Kong logs voor errors:
   ```bash
   docker-compose logs kong
   ```

## Nuttige links

- [Kong Docs](https://docs.konghq.com/)
- [Kong DB-less mode](https://docs.konghq.com/gateway/latest/production/deployment-topologies/db-less-and-declarative-config/)
- [Konga GitHub](https://github.com/pantsel/konga)
- [Kong Admin API Reference](https://docs.konghq.com/gateway/latest/admin-api/)
