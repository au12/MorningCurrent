# API

Set `PUSH_TOKEN` (or *This server's push token* under Settings > Schedule & delivery) to enable it. Every call needs
`Authorization: Bearer <token>`. The upload endpoint is compatible with the earlier Morning Press server, so anything
that pushed editions there can push here.

| Method and path | |
| --- | --- |
| `POST /api/editions` | Store a finished edition. Multipart form: `file` (booklet PDF, required), `reading` (pages-in-order PDF), `date` (YYYY-MM-DD, default today), `title`, `data` (JSON puzzle data). Replaces an existing edition for that date. |
| `GET /api/editions` | Every edition with its pages, title, QA counts and print history. |
| `GET /api/editions/<date>/data` | The puzzle data stored with an edition. |
| `GET /api/status` | Print schedule, next scheduled jobs, whether today's paper exists, running jobs. |
| `POST /api/build` | Start making a paper (form field `date`, default: the next paper). |
| `POST /api/ingest` | Start fetching feeds. |

```bash
curl -H "Authorization: Bearer $PUSH_TOKEN" -F date=2026-11-16 -F title="Vol. I, No. 20" \
     -F file=@booklet.pdf -F reading=@reading.pdf https://news.example.com/api/editions
```

`python -m mc deliver <date>` does the same from a checkout, using `delivery.remote.url` (or `$PRESS_URL`) and
`$PRESS_TOKEN` (or `$REMOTE_TOKEN`, or the remote token saved in Settings). In the container, Settings > Schedule & delivery > *Send to another server*
pushes each new paper automatically.

Public, no token: `GET /read`, `/read/<date>`, `/read/<date>.pdf`, `/archive` (unless the public reader is off) and
`GET /healthz`.
