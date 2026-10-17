-- Run ONCE in the Supabase SQL editor, BEFORE db/schema.sql.
-- Creates the least-privilege role the Streamlit server uses.
--
-- !!! Replace the password below with a long random one (e.g. from a password manager)
-- !!! and put the same password in DATABASE_URL. Do not commit the edited file.

create role lifelink_app login password 'REPLACE_WITH_A_LONG_RANDOM_PASSWORD';
grant usage on schema public to lifelink_app;
