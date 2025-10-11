# Kong & Konga - Fix voor Apple Silicon (M1/M2)

## Probleem

Bij het opstarten van Konga op Apple Silicon (ARM64) krijg je de volgende errors:

1. **Platform incompatibiliteit**: 
   ```
   image with reference pantsel/konga:latest was found but does not provide 
   the specified platform (linux/arm64)
   ```

2. **PostgreSQL versie incompatibiliteit**:
   - Konga (gebaseerd op oude Sails.js ORM) werkt niet met PostgreSQL 13+
   - Error: `column r.consrc does not exist`

3. **Database initialisatie probleem**:
   - PostgreSQL 9.6 ondersteunt geen `scram-sha-256` authenticatie
   - `KONGA_AUTO_MIGRATE` werkt niet betrouwbaar

## Oplossing

### 1. Platform fix
Verander de platform setting van `linux/arm64` naar `linux/amd64`:

```yaml
konga:
  image: pantsel/konga:latest
  container_name: dp_konga
  platform: linux/amd64  # ← Gebruik amd64 emulatie op M1/M2
```

### 2. PostgreSQL downgrade
Gebruik PostgreSQL 9.6 voor de Konga database:

```yaml
postgres_konga:
  image: postgres:9.6-alpine  # ← Downgrade van 13 naar 9.6
  environment:
    POSTGRES_USER: konga
    POSTGRES_PASSWORD: konga
    POSTGRES_DB: konga
    # Verwijder POSTGRES_INITDB_ARGS (scram-sha-256 niet ondersteund in 9.6)
```

### 3. Handmatige database initialisatie
Voer eenmalig het prepare commando uit:

```bash
# Na eerste keer opstarten van postgres_konga:
docker-compose run --rm konga -c prepare -a postgres \
  -u postgresql://konga:konga@postgres_konga:5432/konga
```

## Complete setup stappen

### 1. Start de services
```bash
cd /Users/leeum21/Documents/Werk/Projects/data-platform
docker-compose --profile standard up -d postgres_konga kong
```

### 2. Wacht tot postgres_konga healthy is
```bash
docker-compose ps postgres_konga
# Wacht tot "healthy" status
```

### 3. Initialiseer Konga database
```bash
docker-compose run --rm konga -c prepare -a postgres \
  -u postgresql://konga:konga@postgres_konga:5432/konga
```

Output moet eindigen met:
```
debug: Database migrations completed!
```

### 4. Start Konga
```bash
docker-compose up -d konga
```

### 5. Controleer status
```bash
docker-compose ps | grep -E "(konga|kong)"
```

Alle services moeten "Up" zijn:
- ✅ dp_kong: Up (healthy)
- ✅ dp_postgres_konga: Up (healthy)
- ✅ dp_konga: Up

### 6. Open Konga
Open http://localhost:1337 in je browser. Je wordt doorgestuurd naar `/register`.

## Eerste gebruik

### 1. Registreer admin account
- **Username**: admin
- **Email**: admin@example.com
- **Password**: [kies een sterk wachtwoord]

### 2. Login met je nieuwe account

### 3. Voeg Kong connectie toe
1. Klik op "CONNECTIONS" → "NEW CONNECTION"
2. Vul in:
   - **Name**: Local Kong
   - **Kong Admin URL**: `http://kong:8001`
3. Klik "CREATE CONNECTION"

### 4. Activeer de connectie
Klik op "ACTIVATE" bij de zojuist aangemaakte connectie.

Nu kun je Kong beheren via Konga! 🎉

## Troubleshooting

### Konga start niet op
```bash
# Bekijk logs
docker-compose logs konga

# Als er database errors zijn, herinitialiseer:
docker-compose down konga
docker volume rm data-platform_konga_data
docker-compose run --rm konga -c prepare -a postgres \
  -u postgresql://konga:konga@postgres_konga:5432/konga
docker-compose up -d konga
```

### Kong Admin API niet bereikbaar vanuit Konga
Gebruik `http://kong:8001` (NIET `http://localhost:8001`). Containers gebruiken Docker netwerk namen.

### Database verbinding problemen
```bash
# Test database connectie
docker-compose exec postgres_konga psql -U konga -d konga -c "SELECT version();"

# Bekijk tabellen
docker-compose exec postgres_konga psql -U konga -d konga -c "\dt"
```

## Waarom deze fixes nodig zijn?

### pantsel/konga is verouderd
- Laatste update: 2019
- Geen ARM64 support
- Gebaseerd op oude Sails.js versie
- Werkt niet met moderne PostgreSQL versies

### Alternatieve oplossingen

#### Optie 1: Gebruik Kong Manager (enterprise)
Kong heeft een ingebouwde UI, maar alleen in de Enterprise versie.

#### Optie 2: Gebruik Kong Deck + YAML
Beheer Kong via YAML configuratie met [deck](https://docs.konghq.com/deck/):
```bash
brew install deck
deck dump --kong-addr http://localhost:8001
```

#### Optie 3: Directe Admin API calls
```bash
# Services
curl http://localhost:8001/services

# Routes
curl http://localhost:8001/routes

# Plugins
curl http://localhost:8001/plugins
```

#### Optie 4: Insomnia Kong plugin
Download [Insomnia](https://insomnia.rest/) en gebruik de Kong plugin voor grafische Kong management.

## Performance overwegingen

### PostgreSQL 9.6 is oud
⚠️ **Let op**: PostgreSQL 9.6 is end-of-life (2021). Alleen gebruiken voor Konga!

Voor productie:
- Gebruik een aparte, geïsoleerde postgres_konga instance
- Houd het volume klein (alleen Konga metadata)
- Overweeg alternatieven zoals Kong Deck voor GitOps workflows

### AMD64 emulatie op ARM64
De `platform: linux/amd64` setting draait de container in emulatie mode op M1/M2 Macs. Dit is langzamer dan native ARM64, maar voor Konga (alleen admin UI) is dit acceptabel.

## Productie aanbevelingen

Voor productie gebruik:
1. **Kong in database mode** (zie `kong/docs/kong-with-db.md`)
2. **Separate Konga instance** (niet op dezelfde server als Kong)
3. **Backup van Konga database** (bevat je configuratie en gebruikers)
4. **HTTPS** voor Konga UI
5. **Firewall regels** om Konga alleen binnen je netwerk toegankelijk te maken

## Nuttige commando's

```bash
# Herstart alles
docker-compose restart postgres_konga kong konga

# Logs volgen
docker-compose logs -f konga

# Database backup
docker-compose exec postgres_konga pg_dump -U konga konga > konga-backup.sql

# Database restore
cat konga-backup.sql | docker-compose exec -T postgres_konga psql -U konga konga

# Volledig resetten
docker-compose down postgres_konga konga
docker volume rm data-platform_konga_pgdata data-platform_konga_data
# Dan de setup stappen opnieuw uitvoeren
```
