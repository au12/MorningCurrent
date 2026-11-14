# Moving from Morning Press

Morning Press was the earlier print-server container: it received each night's edition over the push API and printed
it on schedule. The Morning Current container replaces it and keeps its API, data and settings.

1. Stop the `morning-press` container.
2. Install `morning-current` (Unraid template, compose file or `docker run`) with its **Data** path pointing at the old
   Morning Press appdata folder (for example `/mnt/user/appdata/morning-press`), or copy that folder's contents into
   the new one. Keep the same `ADMIN_PASSWORD` and `PUSH_TOKEN`; the old `CUPS_SERVER` and `TZ` variables still work.
3. Start it. On the first start the old files are moved into the new layout (`editions/<date>/booklet.pdf`,
   `reading.pdf`, `meta.json`), the printer and print-schedule settings move into `config.yaml`, and a stored admin
   password is kept. The reader, archive and print history carry over.

A migrated server behaves exactly as Morning Press did: it **receives** editions and prints them, and its own nightly
build is **off**, so it never competes with the routine that pushes to it. Nothing about the sender has to change: the
`/api/editions` endpoint and token are the same.

When you want the container to make the paper itself, open Settings > Paper & place (set the place for the almanac),
review Sources and Layout, then turn on *Make a paper every day* under Schedule & delivery. At that point stop the
external routine that pushed editions (for the original household, a scheduled Claude Code task), or both will
produce a paper for the same date and the later one wins. To keep Claude writing the stories, choose Claude under
Settings > AI.
