-- Initialisatie voor Konga database op aparte postgres_konga instance
-- Dit script draait NIET op de hoofddatabase, maar dient als referentie.
-- De postgres_konga container maakt automatisch de user en database aan via ENV vars,
-- maar dit script documenteert de structuur en kan gebruikt worden voor extra setup.

-- De volgende stappen worden automatisch gedaan door postgres_konga container:
-- CREATE USER konga WITH PASSWORD 'konga';
-- CREATE DATABASE konga OWNER konga;

-- Als je wilt, kun je deze queries handmatig draaien op postgres_konga:
-- psql -h localhost -p 5433 -U konga -d konga

-- Extra security: zorg dat alleen konga user toegang heeft
-- Dit is optioneel, maar recommended voor productie
\c konga;

-- Verleen alle rechten op public schema aan konga user
GRANT ALL PRIVILEGES ON SCHEMA public TO konga;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO konga;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO konga;

-- Zorg dat toekomstige tabellen ook toegankelijk zijn
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO konga;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO konga;
