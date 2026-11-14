# Third-party notices

The Morning Current's own code and data are MIT-licensed (see [LICENSE](LICENSE)). The repository
also bundles the following works under their own licenses:

| What | Where | License |
| --- | --- | --- |
| Libre Franklin, Playfair Display, Source Serif 4, UnifrakturMaguntia (fonts) | `mc/data/fonts/` | SIL Open Font License 1.1 (license files alongside) |
| PDF.js 4.10.38 | `mc/web/static/vendor/pdf*.mjs` | Apache-2.0 (`LICENSE.pdfjs.txt`) |
| StPageFlip 2.0.7 | `mc/web/static/vendor/page-flip.browser.js` | MIT |

The quotation corpus (`mc/data/quotes.json`) holds short lines by authors whose works are in the
public domain, attributed to their sources.

The container image additionally downloads, at build time:

- **WordNet 3.0** (Princeton University), used for crossword clues and the word of the day, under
  the WordNet license (BSD-style);
- the **CMU Pronouncing Dictionary**, used for respellings, under a BSD-style license;
- a headless **Chromium** build from the Playwright project, used to lay out and print the pages,
  under the Chromium licenses;
- the Python packages in [requirements.txt](requirements.txt), each under its own license.
  Note that `wordfreq` ships word-frequency data under CC BY-SA 4.0.

## Content printed in the paper

Articles printed in full come only from sources marked public domain or Creative Commons in
Settings > Sources, with their attribution and license in each story's source box; copyrighted
sources are reduced to the headline, the publisher's own feed summary and a link. The licenses in
the bundled source packs were checked in November 2026, but you are responsible for checking the
terms of any source you print. See [docs/sources-and-licensing.md](docs/sources-and-licensing.md).
