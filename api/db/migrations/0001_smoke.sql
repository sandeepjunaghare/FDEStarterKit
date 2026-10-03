-- Table for POST /smoke. Rows never persist: the endpoint rolls its transaction back.
create table if not exists smoke_checks (
    id bigint generated always as identity primary key,
    note text not null,
    embedding vector(3) not null,
    created_at timestamptz not null default now()
);

-- RLS on, no policies: blocks Supabase's public REST API; the postgres owner role is unaffected.
alter table smoke_checks enable row level security;
