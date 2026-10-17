-- ============================================================================
-- LifeLink — PostgreSQL / Supabase schema  (schema version 1)
--
-- Safe to run more than once (idempotent). It NEVER drops or truncates data.
-- Run it in the Supabase SQL editor (or with scripts/init_db.py).
--
-- Security model
--   * Row-Level Security is ENABLED on every table.
--   * The Supabase public roles (anon, authenticated) get NO access at all, so
--     the auto-generated Supabase REST API can never read donor/patient rows.
--   * The Streamlit server connects as the least-privilege role `lifelink_app`
--     (create it first — see README, step "Create the app database role").
--   * The service_role key is never used or needed by this app.
-- ============================================================================

create table if not exists schema_migrations (
    version     integer primary key,
    applied_at  timestamptz not null default now()
);

-- ── donors ───────────────────────────────────────────────────────────────────
create table if not exists donors (
    id               uuid primary key,
    public_id        text        not null unique,            -- e.g. LL-D-7K2M9Q4X (shown to people)
    name             text        not null check (char_length(name) between 2 and 80),
    age              integer     not null check (age between 18 and 65),
    gender           text        not null check (gender in ('Male','Female','Other')),
    blood_type       text        not null check (blood_type in ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    donation_type    text        not null check (donation_type in ('Blood','Organ')),
    organs           jsonb       not null default '[]'::jsonb,  -- list of organ names (Organ donors)
    city             text        not null check (char_length(city) between 2 and 60),
    state            text        not null,
    phone            text        not null,                    -- as entered (private)
    phone_norm       text        not null,                    -- last 10 digits, used to block duplicates
    email            text        not null default '',
    medical_notes    text        not null default '' check (char_length(medical_notes) <= 1000),
    available        boolean     not null default true,
    access_code_hash text        not null,                    -- PBKDF2 hash of the donor's private access code
    submit_key       text        unique,                      -- idempotency key: blocks double submits
    consent_at       timestamptz not null,
    registered_at    timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create unique index if not exists donors_phone_norm_key on donors (phone_norm);
create index if not exists donors_blood_idx        on donors (blood_type);
create index if not exists donors_state_city_idx   on donors (state, city);
create index if not exists donors_available_idx    on donors (available);

-- ── recipients (blood / organ requests) ─────────────────────────────────────
create table if not exists recipients (
    id               uuid primary key,
    public_id        text        not null unique,            -- e.g. LL-R-3H8TQW2N
    name             text        not null check (char_length(name) between 2 and 80),  -- patient name (private)
    age              integer     not null check (age between 0 and 120),
    gender           text        not null check (gender in ('Male','Female','Other')),
    blood_type       text        not null check (blood_type in ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    need_type        text        not null check (need_type in ('Blood','Organ')),
    organ_needed     text        not null default '',
    city             text        not null check (char_length(city) between 2 and 60),
    state            text        not null,
    hospital         text        not null check (char_length(hospital) between 2 and 120),
    phone            text        not null,
    phone_norm       text        not null,
    email            text        not null default '',
    urgency          text        not null check (urgency in
                        ('Critical (< 24 hrs)','Urgent (1–3 days)','Moderate (within a week)','Stable')),
    medical_notes    text        not null default '' check (char_length(medical_notes) <= 1000),
    status           text        not null default 'Open'
                        check (status in ('Open','In Progress','Fulfilled','Cancelled')),
    access_code_hash text        not null,
    submit_key       text        unique,
    consent_at       timestamptz not null,
    posted_at        timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);
create index if not exists recipients_status_idx  on recipients (status);
create index if not exists recipients_blood_idx   on recipients (blood_type);
create index if not exists recipients_phone_idx   on recipients (phone_norm);
create index if not exists recipients_posted_idx  on recipients (posted_at);

-- ── matches ─────────────────────────────────────────────────────────────────
-- score   : the existing algorithm's total_score (0-100, unchanged weights)
-- details : JSON {schema_version, reasons[], blood_score, location_score,
--                 urgency_score, availability_score}
create table if not exists matches (
    id            uuid primary key,
    public_id     text        not null unique,               -- e.g. LL-M-5N2VX8KD
    donor_id      uuid        not null references donors(id)     on delete cascade,
    recipient_id  uuid        not null references recipients(id) on delete cascade,
    score         numeric(5,1) not null check (score between 0 and 100),
    details       jsonb       not null default '{}'::jsonb,
    status        text        not null default 'Pending Contact'
                     check (status in ('Pending Contact','Contacted','In Progress','Completed','Failed')),
    matched_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (donor_id, recipient_id)                          -- one saved match per pair
);
create index if not exists matches_status_idx    on matches (status);
create index if not exists matches_recipient_idx on matches (recipient_id);
create index if not exists matches_matched_idx   on matches (matched_at);

-- ── audit_log: administrator actions ────────────────────────────────────────
create table if not exists audit_log (
    id         uuid primary key,
    at         timestamptz not null default now(),
    actor      text        not null default 'admin',
    action     text        not null,
    entity     text        not null default '',
    entity_id  text        not null default '',
    detail     text        not null default ''
);
create index if not exists audit_log_at_idx on audit_log (at);

-- ── auth_attempts: throttling for admin login and private access codes ─────
create table if not exists auth_attempts (
    id            uuid primary key,
    scope         text        not null,                      -- 'admin' or 'donor:<id>' / 'recipient:<id>'
    success       boolean     not null,
    attempted_at  timestamptz not null default now()
);
create index if not exists auth_attempts_scope_idx on auth_attempts (scope, attempted_at);

insert into schema_migrations (version) values (1) on conflict (version) do nothing;

-- ============================================================================
-- Row-Level Security + least-privilege grants
-- ============================================================================
alter table donors          enable row level security;
alter table recipients      enable row level security;
alter table matches         enable row level security;
alter table audit_log       enable row level security;
alter table auth_attempts   enable row level security;
alter table schema_migrations enable row level security;

do $$
declare t text;
begin
  -- 1. Supabase's public API roles get nothing.
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke all on all tables in schema public from anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    revoke all on all tables in schema public from authenticated;
  end if;

  -- 2. The Streamlit server role gets exactly what the app needs.
  if exists (select 1 from pg_roles where rolname = 'lifelink_app') then
    grant usage on schema public to lifelink_app;
    grant select, insert, update, delete on donors, recipients, matches to lifelink_app;
    grant select, insert on audit_log to lifelink_app;
    grant select, insert, delete on auth_attempts to lifelink_app;
    grant select on schema_migrations to lifelink_app;

    foreach t in array array['donors','recipients','matches','audit_log','auth_attempts'] loop
      execute format('drop policy if exists lifelink_app_all on %I', t);
      execute format('create policy lifelink_app_all on %I for all to lifelink_app using (true) with check (true)', t);
    end loop;
    drop policy if exists lifelink_app_read on schema_migrations;
    create policy lifelink_app_read on schema_migrations for select to lifelink_app using (true);
  else
    raise notice 'Role lifelink_app does not exist yet. Create it (see README) and re-run this script to apply grants/policies.';
  end if;
end $$;
