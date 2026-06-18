create table if not exists private.study_users (
  username_normalized text primary key,
  display_name text not null,
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

revoke all on private.study_users from public, anon, authenticated;

with ranked_profiles as (
  select
    lower(regexp_replace(trim(display_name), '\s+', ' ', 'g')) as username_normalized,
    display_name,
    state,
    created_at,
    updated_at,
    row_number() over (
      partition by lower(regexp_replace(trim(display_name), '\s+', ' ', 'g'))
      order by
        (
          jsonb_array_length(coalesce(state -> 'history', '[]'::jsonb)) +
          jsonb_array_length(coalesce(state -> 'favorites', '[]'::jsonb))
        ) desc,
        updated_at desc
    ) as rank
  from private.study_profiles
  where char_length(trim(display_name)) between 1 and 32
)
insert into private.study_users (
  username_normalized,
  display_name,
  state,
  created_at,
  updated_at
)
select
  username_normalized,
  display_name,
  state,
  created_at,
  updated_at
from ranked_profiles
where rank = 1
on conflict (username_normalized) do nothing;

create or replace function public.load_study_user(p_username text)
returns table (
  display_name text,
  state jsonb,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  normalized_username text;
begin
  normalized_username := lower(regexp_replace(trim(p_username), '\s+', ' ', 'g'));

  if normalized_username is null or char_length(normalized_username) < 1 or char_length(normalized_username) > 32 then
    raise exception 'Invalid username';
  end if;

  return query
  select users.display_name, users.state, users.updated_at
  from private.study_users as users
  where users.username_normalized = normalized_username;
end;
$$;

create or replace function public.save_study_user(
  p_username text,
  p_display_name text,
  p_state jsonb
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  normalized_username text;
begin
  normalized_username := lower(regexp_replace(trim(p_username), '\s+', ' ', 'g'));

  if normalized_username is null or char_length(normalized_username) < 1 or char_length(normalized_username) > 32 then
    raise exception 'Invalid username';
  end if;

  if p_display_name is null or char_length(trim(p_display_name)) < 1 or char_length(p_display_name) > 32 then
    raise exception 'Invalid display name';
  end if;

  if p_state is null or octet_length(p_state::text) > 1000000 then
    raise exception 'Invalid profile state';
  end if;

  insert into private.study_users (username_normalized, display_name, state)
  values (normalized_username, trim(p_display_name), p_state)
  on conflict (username_normalized) do update
  set display_name = excluded.display_name,
      state = excluded.state,
      updated_at = now();
end;
$$;

revoke all on function public.load_study_user(text) from public;
revoke all on function public.save_study_user(text, text, jsonb) from public;
grant execute on function public.load_study_user(text) to anon, authenticated;
grant execute on function public.save_study_user(text, text, jsonb) to anon, authenticated;
