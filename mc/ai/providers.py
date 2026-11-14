"""AI providers behind one small interface.

    p = get()                         # from Settings > AI (None when AI is off)
    out = p.complete(system, prompt, schema=STORY_SCHEMA, max_tokens=4000)
    out.data                          # parsed JSON (when a schema was given), else out.text
    out.fetched                       # {url: text} pages the model fetched with web tools (Claude research)

Claude goes through the official SDK (structured outputs, server-side web search and fetch). Anything
that speaks the OpenAI chat-completions API (Ollama, LM Studio, vLLM, OpenAI) works through `openai`.
Every call is metered against the per-edition budget; when it runs out, BudgetExceeded is raised and
the build carries on without AI.
"""
import json
import re
import time

from .. import config, secrets

# USD per million tokens (input, output); override or extend in Settings > AI > prices.
DEFAULT_PRICES = {
    'claude-haiku-5-5': (0.10, 0.50),
    'claude-sonnet-5-5': (2.0, 10.0),
    'claude-sonnet-5': (2.0, 10.0),
    'claude-opus-5-5': (4.0, 20.0),
    'claude-fable-5-2': (10.0, 50.0),
    'claude-fable-5-1': (10.0, 50.0),
    'claude-haiku-4-5': (1.0, 5.0),
    'claude-sonnet-4-6': (3.0, 15.0),
}
SEARCH_PRICE = 0.01          # USD per web search


class BudgetExceeded(Exception):
    pass


class AIError(Exception):
    pass


class Budget:
    def __init__(self, limit_usd):
        self.limit = float(limit_usd or 0)
        self.spent = 0.0
        self.calls = 0
        self.tokens_in = self.tokens_out = self.searches = 0

    def add(self, cost, tin=0, tout=0, searches=0):
        self.spent += cost
        self.calls += 1
        self.tokens_in += tin
        self.tokens_out += tout
        self.searches += searches

    def check(self, reserve=0.0):
        if self.limit and self.spent + reserve > self.limit:
            raise BudgetExceeded(f'AI budget used: ${self.spent:.2f} of ${self.limit:.2f}')

    def summary(self):
        return dict(spent_usd=round(self.spent, 4), limit_usd=self.limit, calls=self.calls, input_tokens=self.tokens_in,
                    output_tokens=self.tokens_out, searches=self.searches)


class Result:
    def __init__(self, text='', data=None, fetched=None, searched=None):
        self.text, self.data, self.fetched, self.searched = text, data, fetched or {}, searched or []


def parse_json(text):
    """The first JSON object or array in a model's reply (tolerates code fences and prose around it)."""
    text = text.strip()
    m = re.search(r'```(?:json)?\s*(.+?)```', text, re.S)
    if m:
        text = m.group(1)
    for opener, closer in (('{', '}'), ('[', ']')):
        i = text.find(opener)
        j = text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise AIError('reply was not valid JSON')


class Provider:
    name = 'none'

    def __init__(self, cfg, budget):
        self.cfg, self.budget = cfg, budget

    def price(self):
        prices = dict(DEFAULT_PRICES)
        prices.update({k: tuple(v) for k, v in (self.cfg.ai.prices or {}).items()})
        return prices.get(self.cfg.ai.model, (3.0, 15.0))

    def complete(self, system, prompt, schema=None, max_tokens=4000, tools=None):
        raise NotImplementedError


class Claude(Provider):
    name = 'claude'

    def __init__(self, cfg, budget):
        super().__init__(cfg, budget)
        import anthropic
        key = secrets.get('anthropic_api_key')
        if not key:
            raise AIError('no Anthropic API key (Settings > AI, or $ANTHROPIC_API_KEY)')
        self.client = anthropic.Anthropic(api_key=key, max_retries=3, timeout=600)
        self.anthropic = anthropic

    def complete(self, system, prompt, schema=None, max_tokens=4000, tools=None):
        self.budget.check(0.02)
        kw = dict(model=self.cfg.ai.model, max_tokens=max_tokens, system=system,
                  messages=[{'role': 'user', 'content': prompt}])
        if self.cfg.ai.temperature is not None and not tools:
            kw['temperature'] = self.cfg.ai.temperature
        if schema and not tools:
            kw['output_config'] = {'format': {'type': 'json_schema', 'schema': schema}}
        if tools:
            kw['tools'] = tools
        fetched, searched, texts = {}, [], []
        for turn in range(8):                  # server tools may pause a long turn; continue it
            try:
                resp = self.client.messages.create(**kw)
            except self.anthropic.BadRequestError as e:
                msg = str(e)
                if tools and 'beta' in msg.lower() and 'extra_headers' not in kw:
                    kw['extra_headers'] = {'anthropic-beta': 'web-fetch-2025-09-10'}
                    continue
                if 'output_config' in kw and ('output_config' in msg or 'json_schema' in msg):
                    kw.pop('output_config')     # older model or endpoint: ask for JSON in words instead
                    kw['messages'][0]['content'] = prompt + '\n\nReply with only the JSON object.'
                    continue
                raise AIError(msg[:300])
            except self.anthropic.APIError as e:
                raise AIError(f'{type(e).__name__}: {str(e)[:300]}')
            u = resp.usage
            n_search = 0
            stu = getattr(u, 'server_tool_use', None)
            if stu is not None:
                n_search = getattr(stu, 'web_search_requests', 0) or 0
            pin, pout = self.price()
            tin = (u.input_tokens or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0) + (getattr(u, 'cache_read_input_tokens', 0) or 0)
            cost = tin / 1e6 * pin + (u.output_tokens or 0) / 1e6 * pout + n_search * SEARCH_PRICE
            self.budget.add(cost, tin, u.output_tokens or 0, n_search)
            for b in resp.content:
                t = getattr(b, 'type', '')
                if t == 'text':
                    texts.append(b.text)
                elif t == 'web_fetch_tool_result':
                    c = getattr(b, 'content', None)
                    url = getattr(c, 'url', None)
                    doc = getattr(c, 'content', None)
                    src = getattr(doc, 'source', None)
                    data = getattr(src, 'data', None)
                    if url and isinstance(data, str):
                        fetched[url] = data
                elif t == 'web_search_tool_result':
                    for r in getattr(b, 'content', None) or []:
                        if getattr(r, 'url', None):
                            searched.append(dict(url=r.url, title=getattr(r, 'title', ''), age=getattr(r, 'page_age', '')))
            if resp.stop_reason == 'pause_turn':
                kw['messages'] = kw['messages'][:1] + [{'role': 'assistant', 'content': resp.content}]
                continue
            break
        text = '\n'.join(texts).strip()
        data = parse_json(text) if schema else None
        return Result(text=text, data=data, fetched=fetched, searched=searched)


class OpenAICompatible(Provider):
    name = 'openai'

    def __init__(self, cfg, budget):
        super().__init__(cfg, budget)
        import httpx
        self.base = (cfg.ai.base_url or 'https://api.openai.com/v1').rstrip('/')
        self.key = secrets.get('openai_api_key')
        self.http = httpx.Client(timeout=900)

    def complete(self, system, prompt, schema=None, max_tokens=4000, tools=None):
        if tools:
            raise AIError('web research needs the Claude provider')
        self.budget.check(0.0)
        body = dict(model=self.cfg.ai.model, max_tokens=max_tokens, temperature=self.cfg.ai.temperature,
                    messages=[{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}])
        if schema:
            body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'output', 'schema': schema}}
        headers = {'Authorization': f'Bearer {self.key}'} if self.key else {}
        for attempt in range(3):
            r = self.http.post(f'{self.base}/chat/completions', json=body, headers=headers)
            if r.status_code == 400 and 'response_format' in body:
                body.pop('response_format')     # servers without JSON-schema support: ask in words
                body['messages'][1]['content'] = prompt + '\n\nReply with only the JSON object.'
                continue
            if r.status_code >= 500 or r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            break
        if r.status_code >= 400:
            raise AIError(f'HTTP {r.status_code}: {r.text[:300]}')
        j = r.json()
        u = j.get('usage') or {}
        pin, pout = self.price() if self.cfg.ai.model in (self.cfg.ai.prices or {}) else (0.0, 0.0)
        self.budget.add(u.get('prompt_tokens', 0) / 1e6 * pin + u.get('completion_tokens', 0) / 1e6 * pout,
                        u.get('prompt_tokens', 0), u.get('completion_tokens', 0))
        text = j['choices'][0]['message'].get('content') or ''
        return Result(text=text, data=parse_json(text) if schema else None)


def get(budget=None, cfg=None):
    """The configured provider, or None when AI is off."""
    cfg = cfg or config.load()
    budget = budget or Budget(cfg.ai.max_cost_usd)
    if cfg.ai.provider == 'claude':
        return Claude(cfg, budget)
    if cfg.ai.provider == 'openai':
        return OpenAICompatible(cfg, budget)
    return None


def test_connection(cfg=None):
    """A tiny call to check the key and model (used by the Settings page)."""
    cfg = cfg or config.load()
    p = get(Budget(0.05), cfg)
    if p is None:
        return False, 'AI is off'
    try:
        r = p.complete('You reply with one word.', 'Say OK.', max_tokens=10)
        return True, f'{cfg.ai.model} replied: {r.text[:40]}'
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:300]
