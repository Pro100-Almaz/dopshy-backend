-- Creates the requested accounts directly in the `account` table.
-- Passwords are pre-hashed with this app's exact scheme (bcrypt(HASHING_SALT) -> _hash_salt,
-- then argon2(_hash_salt + plaintext password) -> _hashed_password), generated using the
-- HASHING_SALT currently set in backend/.env. If HASHING_SALT ever changes, these hashes
-- will stop verifying and must be regenerated.
--
-- is_active / is_verified are set to true so these accounts can log in immediately.

INSERT INTO account (username, email, _hashed_password, _hash_salt, role, is_active, is_verified, is_logged_in)
VALUES
    ('superadmin',    'superadmin@dopsy.kz',    '$argon2id$v=19$m=65536,t=3,p=4$pxQiRMh5b42xVkoJYQzhPA$0yTzI1K6WfMucQaE8907aJgxpf2MjmkxppjMwKZrKTs',  '$2b$12$xu/TBAryKbQ7bu8NScwUb.8D4Ju.rBEmTpVZ3thZifa/3GCGJbnWi',  'super_admin',      true, true, false),
    ('fsmanager',     'fsmanager@dopsy.kz',     '$argon2id$v=19$m=65536,t=3,p=4$IySkdC7lXKuVsta6V0pprQ$9v1S7PkSb0ZE4JWSHtIE4ODEF/stBZ1hdD7hnaqmfOU',  '$2b$12$u/XO/9YjC4lMMuZZfQREbO8o34kWow9zs4CDPWiiwSc1I1dzWfIJ2', 'football_manager', true, true, false),
    ('boxmanager',    'boxmanager@dopsy.kz',    '$argon2id$v=19$m=65536,t=3,p=4$U6q1VmothXAuBcD4HyOEEA$S8vfHjQBpmjNgpW5xgowDPt02d5EsWVwNQFBeeSCcRM',  '$2b$12$Cfjnwxt7EsjQGbd895GCw.GR1AT4JJnJbbsygTQPxlOZtZebHEnsS', 'boxing_manager',   true, true, false),
    ('arenamanager',  'arenamanager@dopsy.kz',  '$argon2id$v=19$m=65536,t=3,p=4$qtXam1OKUYqx9t5by5nT+g$ItpijOMi+EfAGOpicTRvnRKrRhkyUPPPJ3JtCgKogZ4', '$2b$12$0g61BL4DVhtBwaXJvXgdHuNrKWQM9gspgqUkCovohKTV.4Py95JLC', 'admin',            true, true, false),
    ('arenamanager2', 'arenamanager2@dopsy.kz', '$argon2id$v=19$m=65536,t=3,p=4$bO29d25tbW3NWct5z1mLEQ$pIUTMpz+UW1Kcp9e6Glz3HRu5wQwj1RUYzlhZUMqbb0', '$2b$12$i1Huqahc/.If/1KtgqCyyueumDU0imtlO6p9IA2qdzb4HwLzWxqFO', 'arena_manager',    true, true, false);
