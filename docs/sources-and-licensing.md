# Sources and licensing

The paper prints other people's writing, so every source carries a **license** that decides how much of an article
may appear on paper. This is the most important setting on the Sources page.

| License | Tier | Without AI | With AI |
| --- | --- | --- | --- |
| `public-domain` | full | Whole article, trimmed to fit, photos allowed (`images: true`) | Rewritten to the house style |
| `cc-by`, `cc-by-sa`, `cc-by-nc`, `cc-by-nc-sa` | full | Whole article, trimmed to fit, credited "Excerpted. CC BY 4.0" | Rewritten, credited |
| `cc-by-nd`, `cc-by-nc-nd` | verbatim | Unedited text cut only at a paragraph end, headline as published, "This excerpt continues at the source" | Unchanged: no derivatives |
| `copyrighted` | excerpt | The publisher's own headline and feed summary with a QR code | An original short article written from the source |

A per-feed `tier` can override the license's tier (for example `headline` to print only briefs from a feed).
Non-commercial licenses (`-nc`) fit a household paper; don't use them if you distribute the paper commercially.

Every printed story names its source, date and author where known, and its license or the source's attribution line
(`attribution:`), in a box with a QR code to the original. The back page lists every source.

## The bundled packs

Turn packs on in the setup wizard or on the Sources page; each feed can then be edited, disabled or removed.

- **Open science (full text)**, on by default: NASA, NASA Science, NOAA, the National Science Foundation, NIST, USDA
  Agricultural Research Service, U.S. Fish & Wildlife Service, the National Archives' Prologue blog (US federal works,
  public domain) and eLife digests (CC BY).
- **Free to republish (CC BY-ND)**, on by default: The Conversation (several sections), Knowable Magazine, Mongabay.
  These ask that articles not be edited, so they are printed unchanged and cut only at a paragraph end; their
  republishing guidelines also ask not to republish systematically, hence a low `max_per_edition`.
- **Science news (headlines and summaries)**, on by default: ScienceDaily, Phys.org, Quanta, Smithsonian, Ars Technica.
- **Engineering, makers and cars**: IEEE Spectrum, Hackaday, New Atlas, PetaPixel, Hagerty.
- **Good news and curiosities**: Good News Network, Reasons to be Cheerful, Atlas Obscura, The Public Domain Review.

The licenses were checked in November 2026. Terms change; check a source's own terms before relying on them,
especially before raising a source above `copyrighted`.

Some details handled automatically:

- US government sites often host third-party photos. A photo prints only from a feed with `images: true`, and one
  credited to another agency, a wire service or a photographer is skipped.
- Feeds that carry only a summary have the article page fetched (`fetch_full_text`), honoring robots.txt, with a pause
  between requests to the same host and a descriptive user agent.
- Wikipedia "On this day" and featured-article extracts (CC BY-SA) can fill short columns (`filler_wikipedia`).

## Adding your own

On the Sources page add a feed URL (RSS or Atom), its license and optionally a default category, or import an OPML
file from a feed reader (imported feeds start as `copyrighted`). **Test** shows what the feed returns.

Raise the license only when the publisher says so explicitly: a Creative Commons notice on the article pages, a
"republish this article" policy, or a government work. When in doubt leave it at `copyrighted`; the paper still prints
the headline, summary and QR code, and with AI on, an original short article.

## What the filters skip

Before a story can run it must be recent (`recency_days`; nothing older than `recency_exception_days`), not already
printed, not a duplicate of another source's version of the same story, and its headline must not hit the blocklist
(crime, courts, disasters, war and politics, sensational and celebrity terms, crypto...) or fall below the tone
threshold. Edit the lists under Settings > Content & filters; `allowlist` rescues phrases such as "Dead Sea". The editor's
desk shows what was filtered and why, and anything can be restored or pinned by hand.
