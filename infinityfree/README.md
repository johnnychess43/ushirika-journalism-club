# InfinityFree version — Ushirika Journalism Club

This directory is the PHP/MySQL migration starter for InfinityFree. The original Flask application remains untouched in the repository.

## Current migration scope

- Member registration and sign-in
- Secure password hashing
- CSRF-protected forms
- Member dashboard
- Article submission
- Published articles
- Events
- Forums
- Member accounts and role field
- MySQL schema
- Responsive mobile/desktop interface

## InfinityFree setup

1. Create the free hosting account and add `ushirikajournalisimclub.world` as your domain.
2. Create a MySQL database in the InfinityFree control panel.
3. Open `config.php` and replace the four `YOUR_MYSQL_*` values with the database host, name, username and password supplied by InfinityFree.
4. Import `schema.sql` into the new database using phpMyAdmin.
5. Upload the contents of this `infinityfree` directory into the domain's web root (`htdocs`).
6. Open the domain and test registration, login, article submission, events and forums.

Do not upload real passwords, API keys or private database credentials to GitHub. For production, place credentials only in the hosting configuration where supported. The current `config.php` contains placeholders only.

## Important

The Flask/Render version remains available as the source implementation while this PHP/MySQL version is migrated feature-by-feature. Do not delete the Flask application until the InfinityFree version has been fully tested.
