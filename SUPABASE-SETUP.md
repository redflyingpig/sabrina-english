# Username profile sync setup

The website uses a learning username instead of accounts or passwords. Entering the same username on any device loads the same cloud record.

The free Supabase project is connected:

- Project ref: `ghxriablpgkifodeiwxb`
- Region: Singapore (`ap-southeast-1`)
- Compute: Nano (Free Plan)

Database changes are tracked in `supabase/migrations/` and deployed with:

```sh
npx supabase db push --linked
```

The anon key in `index.html` is intended for browser use. Never place a service-role key in this website.

## How identity works

- Usernames are trimmed, spaces are normalized, and matching is case-insensitive.
- The URL uses a fragment such as `#user=Sabrina`.
- Anyone who knows a username can read and change that profile because there is no password.
- Older private-link profiles are migrated by username. If several old profiles used the same display name, the profile containing the most learned and favorite items is selected.
- Learning data remains in localStorage when offline and syncs when the cloud connection is available.
