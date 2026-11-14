# The Morning Current: a printed morning newspaper, made nightly from RSS feeds.
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="The Morning Current" \
      org.opencontainers.image.description="Makes a printed morning newspaper every night from RSS feeds: stories, almanac and puzzles, with optional Claude writing." \
      org.opencontainers.image.source="https://github.com/au12/MorningCurrent" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    NLTK_DATA=/usr/share/nltk_data \
    MC_CONTAINER=1 \
    MC_DATA=/data \
    PORT=8080 \
    PUID=1000 \
    PGID=1000

# cups-client: lp/lpstat for printing; tini reaps the headless browser's processes; libatomic1: Playwright's driver
RUN apt-get update \
 && apt-get install -y --no-install-recommends cups-client tzdata tini fonts-dejavu-core libatomic1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && playwright install --with-deps --only-shell chromium \
 && rm -rf /var/lib/apt/lists/* /root/.cache

# dictionaries for the crossword clues and the word of the day (WordNet, CMU pronouncing dictionary)
# (NLTK refuses downloads through an HTTP proxy unless told the fixed nltk_data URLs are fine)
RUN NLTK_ALLOW_PROXIED_URLOPEN=1 python -c "import nltk; [nltk.download(p, download_dir='/usr/share/nltk_data', quiet=True, raise_on_error=True) for p in ('wordnet', 'cmudict')]" \
 && chmod -R a+rX /usr/share/nltk_data

COPY mc/ /app/mc/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh && python -m compileall -q /app/mc

VOLUME /data
EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8080'), timeout=4)"

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["python", "-m", "mc", "serve"]
