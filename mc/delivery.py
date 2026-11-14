"""Getting a finished edition out of the building: local printing (CUPS), a folder, email, another
server's push API, and a webhook. The nightly build stores the edition; printing happens later at the
scheduled time (see web/scheduler.py), everything else right after the build."""
import datetime
import json
import os
import re
import shlex
import shutil
import smtplib
import subprocess
from email.message import EmailMessage

from . import config, paths, rules as R, secrets


def edition_files(date):
    d = paths.edition_dir(date)
    return {k: os.path.join(d, f'{k}.pdf') for k in ('booklet', 'reading') if os.path.exists(os.path.join(d, f'{k}.pdf'))}


# ------------------------------------------------------------------ printing
def lp_command(cfg, file, title):
    p = cfg.printer
    cmd = ['lp']
    if p.cups_server:
        cmd += ['-h', p.cups_server]
    if p.printer:
        cmd += ['-d', p.printer]
    cmd += ['-n', str(max(1, int(p.copies or 1))), '-t', title]
    sides = p.sides or R.SIDES
    if sides:
        cmd += ['-o', f'sides={sides}']
    media = p.media or R.SHEET
    if media:
        cmd += ['-o', f'media={media}']
    for opt in shlex.split(p.extra_options or ''):
        cmd += ['-o', opt]
    cmd.append(str(file))
    return cmd


def print_pdf(file, title, cfg=None):
    """Send a PDF to CUPS. Returns (ok, output, job id)."""
    cfg = cfg or config.load()
    if not cfg.printer.printer:
        return False, 'no printer configured', ''
    try:
        r = subprocess.run(lp_command(cfg, file, title), capture_output=True, text=True, timeout=90)
        ok, out = r.returncode == 0, (r.stdout or r.stderr).strip()
    except FileNotFoundError:
        return False, 'the lp command is not installed (cups-client)', ''
    except subprocess.TimeoutExpired:
        return False, 'lp timed out talking to the CUPS server', ''
    m = re.search(r'request id is (\S+)', out)
    return ok, out, m.group(1) if m else ''


def cups_queues(server):
    cmd = ['lpstat'] + (['-h', server] if server else []) + ['-a']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return False, [], 'lpstat is not installed (cups-client)'
    except subprocess.TimeoutExpired:
        return False, [], 'timed out reaching the CUPS server'
    if r.returncode != 0:
        return False, [], (r.stderr or r.stdout).strip()
    return True, [line.split()[0] for line in r.stdout.splitlines() if line.strip()], ''


# ------------------------------------------------------------------ other channels
def to_folder(date, folder):
    os.makedirs(folder, exist_ok=True)
    out = []
    for kind, src in edition_files(date).items():
        dst = os.path.join(folder, f'{re.sub(r"[^A-Za-z0-9]+", "-", R.TITLE).strip("-").lower()}-{date}-{kind}.pdf')
        shutil.copy(src, dst)
        out.append(dst)
    return out


def email(date, cfg=None, subject=None):
    cfg = cfg or config.load()
    e = cfg.delivery.email
    if not (e.enabled and e.smtp_host and e.to and e.sender):
        return False, 'email is not configured'
    msg = EmailMessage()
    msg['Subject'] = subject or f'{R.TITLE} for {date}'
    msg['From'] = e.sender
    msg['To'] = ', '.join(e.to)
    msg.set_content(f'{R.TITLE} for {date} is attached.\n')
    files = edition_files(date)
    for kind in (['reading', 'booklet'] if e.attach == 'both' else [e.attach]):
        if kind in files:
            with open(files[kind], 'rb') as f:
                msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(files[kind]))
    try:
        with smtplib.SMTP(e.smtp_host, e.smtp_port, timeout=60) as s:
            if e.starttls:
                s.starttls()
            if e.username:
                s.login(e.username, secrets.get('smtp_password'))
            s.send_message(msg)
        return True, f'emailed {", ".join(e.to)}'
    except (OSError, smtplib.SMTPException) as ex:
        return False, f'email failed: {ex}'


def remote(date, cfg=None):
    cfg = cfg or config.load()
    r = cfg.delivery.remote
    token = secrets.get('remote_token') or os.environ.get('PRESS_TOKEN', '')
    if not (r.enabled and r.url and token):
        return False, 'remote delivery is not configured'
    import httpx
    files = edition_files(date)
    if 'booklet' not in files:
        return False, 'no booklet to send'
    pz = os.path.join(paths.edition_dir(date), 'puzzles.json')
    meta = os.path.join(paths.edition_dir(date), 'meta.json')
    title = json.load(open(meta)).get('title', '') if os.path.exists(meta) else ''
    data = {'date': date, 'title': title, 'data': open(pz).read() if os.path.exists(pz) else ''}
    up = {'file': ('booklet.pdf', open(files['booklet'], 'rb'), 'application/pdf')}
    if 'reading' in files:
        up['reading'] = ('reading.pdf', open(files['reading'], 'rb'), 'application/pdf')
    for attempt in range(3):
        try:
            resp = httpx.post(r.url, headers={'Authorization': f'Bearer {token}'}, files=up, data=data, timeout=120)
            if resp.status_code < 300:
                return True, f'sent to {r.url}'
            last = f'HTTP {resp.status_code}: {resp.text[:200]}'
        except httpx.HTTPError as ex:
            last = str(ex)
    return False, f'remote delivery failed: {last}'


def webhook(date, result, cfg=None):
    cfg = cfg or config.load()
    if not cfg.delivery.webhook:
        return False, 'no webhook'
    import httpx
    body = {k: result.get(k) for k in ('date', 'number', 'pages', 'lead', 'ok', 'errors', 'cosmetic', 'warnings', 'generator')}
    if cfg.web.base_url:
        body['read_url'] = cfg.web.base_url.rstrip('/') + f'/read/{date}'
    try:
        r = httpx.post(cfg.delivery.webhook, json=body, timeout=30)
        return r.status_code < 300, f'webhook HTTP {r.status_code}'
    except httpx.HTTPError as ex:
        return False, f'webhook failed: {ex}'


def after_build(date, result, log=print):
    """Run every configured delivery channel except printing (which waits for the print schedule)."""
    cfg = config.load()
    report = []
    if cfg.delivery.folder:
        try:
            report.append((True, 'copied to ' + ', '.join(to_folder(date, cfg.delivery.folder))))
        except OSError as e:
            report.append((False, f'folder copy failed: {e}'))
    if cfg.delivery.email.enabled:
        report.append(email(date, cfg))
    if cfg.delivery.remote.enabled:
        report.append(remote(date, cfg))
    if cfg.delivery.webhook:
        report.append(webhook(date, result, cfg))
    for ok, msg in report:
        log(('delivered: ' if ok else 'delivery problem: ') + msg)
    return report


def now():
    return datetime.datetime.now().astimezone()
