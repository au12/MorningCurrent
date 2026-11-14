# AI (optional)

The paper is complete without AI. With it, stories from copyrighted sources become original short articles instead of
headline-and-summary briefs, every story reads in one house style, crossword clues and teasers improve, and (in
research mode) Claude looks beyond your feeds for stories that suit the household.

## Setting it up

Settings > AI:

- **Provider**: `Claude (Anthropic API)` with a key from the Anthropic Console (or `ANTHROPIC_API_KEY`), or
  `OpenAI-compatible` with an **Endpoint** such as `http://ollama:11434/v1` for a local model, `https://api.openai.com/v1`
  for OpenAI, and a key if the endpoint needs one (`OPENAI_API_KEY`).
- **Model**: for Claude, `claude-sonnet-5-5` is a good balance; `claude-haiku-5-5` is the cheapest; `claude-opus-5-5`
  writes best. For a local model, its name as the server knows it.
- **Test the connection** makes a tiny call and shows the reply.

## Modes

**Rewrite** (default): the code picks tonight's stories from your feeds exactly as it does without AI, fetches each
article, and the model writes it to the house style from that text, at the length its page needs. Open-licensed stories
keep their automatic version if the model's attempt fails; CC BY-ND stories are never rewritten.

**Research** (Claude only): before planning, Claude uses web search and web fetch to find about 18 candidate stories
that fit your categories, favourites, reader profile and recency window, avoiding what recent papers ran. The app then
fetches each page itself, screens it like a feed article (tone, duplicates, blocklist) and adds it to the desk as an
editor's pick. Research gets up to 40% of the budget.

## Checks

Every story the model writes is verified against the fetched source before it can print:

- every quote must appear word for word in the source, and its speaker must be named there;
- every number (in text, facts boxes and charts) must appear in the source (small counting numbers excepted).

A story with problems goes back once with the problems listed; whatever still fails is cut sentence by sentence. If
too little survives, the story falls back to its automatic version (or, for a copyrighted source, a summary and QR
code). For teasers the model proposes an arithmetic expression from a story's figures and the code computes the answer.

## Cost

**Budget per paper** (default $1.50) is a hard cap: each call is priced from the token counts the API reports (plus
web searches) and the build stops using AI when the budget is spent, finishing the paper without it. The press room and
each edition's page show what was spent. Prices for unlisted models can be added under `ai.prices` in config.yaml
(`model: [USD per million input tokens, per million output]`).

**House style** replaces the built-in style guide (shown as the placeholder on the AI tab). `reader_profile` under
Content & filters tells the model who it is writing for.

## Writing editions elsewhere

An edition can also be written outside the container (by hand, a script or an agent such as Claude Code), built from a
checkout with `python -m mc build <date>` and pushed to the server's [API](api.md). The original household paper was
made that way; the built-in Claude mode does the same job from inside the container with no separate routine.
