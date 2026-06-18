create extension if not exists pgcrypto with schema extensions;
create schema if not exists private;

create table if not exists private.study_profiles (
  profile_hash text primary key,
  display_name text not null,
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

revoke all on private.study_profiles from public, anon, authenticated;

create or replace function public.load_study_profile(p_profile_key text)
returns table (
  display_name text,
  state jsonb,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_profile_key is null or char_length(p_profile_key) < 36 or char_length(p_profile_key) > 200 then
    raise exception 'Invalid profile key';
  end if;

  return query
  select profiles.display_name, profiles.state, profiles.updated_at
  from private.study_profiles as profiles
  where profiles.profile_hash = encode(extensions.digest(p_profile_key, 'sha256'), 'hex');
end;
$$;

create or replace function public.save_study_profile(
  p_profile_key text,
  p_display_name text,
  p_state jsonb
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_profile_key is null or char_length(p_profile_key) < 36 or char_length(p_profile_key) > 200 then
    raise exception 'Invalid profile key';
  end if;

  if p_display_name is null or char_length(trim(p_display_name)) < 1 or char_length(p_display_name) > 32 then
    raise exception 'Invalid display name';
  end if;

  if p_state is null or octet_length(p_state::text) > 1000000 then
    raise exception 'Invalid profile state';
  end if;

  insert into private.study_profiles (profile_hash, display_name, state)
  values (
    encode(extensions.digest(p_profile_key, 'sha256'), 'hex'),
    trim(p_display_name),
    p_state
  )
  on conflict (profile_hash) do update
  set display_name = excluded.display_name,
      state = excluded.state,
      updated_at = now();
end;
$$;

revoke all on function public.load_study_profile(text) from public;
revoke all on function public.save_study_profile(text, text, jsonb) from public;
grant execute on function public.load_study_profile(text) to anon, authenticated;
grant execute on function public.save_study_profile(text, text, jsonb) to anon, authenticated;
