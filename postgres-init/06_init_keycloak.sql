-- ==============================================================================
-- Keycloak Database Initialization
-- ==============================================================================
-- Keycloak gebruikt een eigen database voor opslag van:
-- - Realm configuratie
-- - Gebruikers en groepen
-- - OAuth clients
-- - Sessions en tokens
-- - Audit logs
--
-- Dit script maakt alleen de database aan. Keycloak zelf maakt de schema's
-- en tabellen aan bij de eerste start.
-- ==============================================================================

-- Maak Keycloak database aan (als deze nog niet bestaat)
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec

-- Verbinding met keycloak database voor verdere setup
\c keycloak

-- Maak een dedicated schema aan voor Keycloak (optioneel, Keycloak gebruikt standaard public)
-- CREATE SCHEMA IF NOT EXISTS keycloak;

-- Grant rechten aan superset user (die wordt gebruikt voor de Keycloak connectie)
GRANT ALL PRIVILEGES ON DATABASE keycloak TO superset;

-- Info bericht
DO $$
BEGIN
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'Keycloak database initialization completed';
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'Database: keycloak';
  RAISE NOTICE 'Owner: superset';
  RAISE NOTICE 'Schema: Keycloak will create tables automatically on first start';
  RAISE NOTICE '=================================================================';
END $$;
