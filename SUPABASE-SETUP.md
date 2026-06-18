# Private profile sync setup

The website uses a private bookmark URL instead of accounts or passwords.

The free Supabase project is connected:

- Project ref: `ghxriablpgkifodeiwxb`
- Region: Singapore (`ap-southeast-1`)
- Compute: Nano (Free Plan)

Database changes are tracked in `supabase/migrations/` and deployed with:

```sh
npx supabase db push --linked
```

The anon key in `index.html` is intended for browser use. Never place a service-role key in this website.

## How privacy works

- The profile link contains a random 192-bit secret after `#`.
- URL fragments are not sent in normal HTTP requests or referrer headers.
- The database stores only a SHA-256 hash of that secret.
- Anyone who has the complete private link can read and change that profile, so the link should be treated like a password.
- Learning data remains in localStorage when offline and syncs when the cloud connection is available.
