from __future__ import annotations
import re, time, urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, parse_qs
from bs4 import BeautifulSoup
import requests
from .core import digest, now, emit, require_permission

BASE = 'http://starskku.com'
BOARD = BASE + '/board/board_list?code=research'
UA = 'STARMetadataAudit/0.1 (+bounded public research metadata; 1 request/3 seconds)'


class BoundedClient:
    def __init__(self, delay=3.0, max_requests=450, max_bytes=100_000_000):
        self.delay = max(3.0, delay); self.limit = max_requests; self.byte_limit = max_bytes
        self.requests = self.bytes = self.failures = 0; self.last = 0.0
        self.receipts = []; self.session = requests.Session(); self.session.headers['User-Agent'] = UA
        self.robots = None
    def get(self, url, max_bytes=16_000_000, robots=False):
        if urlsplit(url).hostname not in ('starskku.com', 'www.starskku.com'):
            raise ValueError('unapproved_source_host')
        if not robots and (self.robots is None or not self.robots.can_fetch(UA, url)):
            raise PermissionError('robots_not_allowed')
        for attempt in range(3):
            if self.requests >= self.limit: raise RuntimeError('request_budget_exhausted')
            time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
            self.last = time.monotonic(); self.requests += 1
            try:
                # Do not follow redirects into unreviewed domains.
                r = self.session.get(url, timeout=(10, 40), stream=True, allow_redirects=False)
                if r.status_code in (429, 500, 502, 503, 504):
                    self.failures += 1
                    self.receipts.append({'url': url, 'status': r.status_code, 'at': now(), 'attempt': attempt + 1})
                    retry = r.headers.get('Retry-After', '')
                    r.close()
                    # Long server backoff is deferred to the next job rather than ignored.
                    if retry and (not retry.isdigit() or int(retry) > 30): raise RuntimeError('retry_deferred')
                    time.sleep(max(2 ** attempt, int(retry) if retry.isdigit() else 0)); continue
                if r.status_code != 200:
                    self.failures += 1; self.receipts.append({'url': url, 'status': r.status_code, 'at': now()})
                    r.close(); raise RuntimeError('source_http_' + str(r.status_code))
                buf = bytearray()
                for chunk in r.iter_content(65536):
                    self.bytes += len(chunk); buf.extend(chunk)
                    if len(buf) > max_bytes:
                        r.close(); raise RuntimeError('response_too_large')
                    if self.bytes > self.byte_limit:
                        r.close(); raise RuntimeError('run_byte_budget_exhausted')
                r.close(); data = bytes(buf)
                self.receipts.append({'url': url, 'status': 200, 'at': now(), 'bytes': len(data), 'sha256': digest(data)})
                return data
            except (requests.Timeout, requests.ConnectionError):
                self.failures += 1; self.receipts.append({'url': url, 'status': 'network_error', 'at': now()})
        raise RuntimeError('source_retry_exhausted')
    def check_robots(self):
        body = self.get(BASE + '/robots.txt', robots=True).decode('utf-8')
        rp = urllib.robotparser.RobotFileParser(); rp.parse(body.splitlines()); self.robots = rp
        crawl = rp.crawl_delay(UA) or rp.crawl_delay('*')
        if crawl: self.delay = max(self.delay, crawl)
        return {'url': BASE + '/robots.txt', 'sha256': digest(body.encode()), 'text': body, 'checked_at': now()}


def parse_listing(body):
    s = BeautifulSoup(body, 'html.parser')
    rows = []
    for a in s.select('.bbs_list .board_tit a[href]'):
        url = urljoin(BASE, a['href']); no = parse_qs(urlsplit(url).query).get('no', [None])[0]
        if no and no.isdigit(): rows.append({'report_id': 'star-' + no, 'post_url': url, 'title': a.get_text(' ', strip=True)})
    pages = [int(a['data-ci-pagination-page']) for a in s.select('a[data-ci-pagination-page]')]
    count = s.select_one('.bbs_num strong')
    return rows, max(pages, default=1), int(count.get_text()) if count else None


def parse_post(body, url):
    s = BeautifulSoup(body, 'html.parser'); title = s.select_one('.view_tit h3'); date = s.select_one('.view_tit p')
    if not title or not date: raise ValueError('post_layout_changed')
    title = title.get_text(' ', strip=True); dt = re.search(r'\d{4}-\d{2}-\d{2}', date.get_text())
    published = re.search(r'발간일\s*:\s*(\d{6})', title)
    attachments = [urljoin(BASE, a['href']) for a in s.select('.extra_cont a[href]')]
    image_sources = [a['src'] for a in s.select('.view_cont img[src]')]
    # data: URLs contain image bytes, not link metadata. Never persist them.
    inline_hashes = [digest(u.encode()) for u in image_sources if u.startswith('data:')]
    images = [urljoin(BASE, u) for u in image_sources if not u.startswith('data:') and len(u) <= 8192
              and urlsplit(urljoin(BASE, u)).scheme in ('http', 'https')]
    # Hash stable content only: the site's dynamic CURRENT_DATE script is excluded.
    content = s.select_one('.view_cont')
    record = {'report_id': 'star-' + parse_qs(urlsplit(url).query)['no'][0], 'post_url': url,
              'title': title, 'company_name': title.split(',')[0].strip(),
              'publication_date': datetime.strptime(published[1], '%y%m%d').date().isoformat() if published else None,
              'publication_date_source': 'post_title' if published else None,
              'posted_date': dt[0] if dt else None, 'posted_time': None,
              'attachment_urls': attachments, 'embedded_image_urls': images,
              'inline_image_count': len(inline_hashes), 'inline_image_sha256': inline_hashes,
              'content_fingerprint': digest({'text': content.get_text(' ', strip=True) if content else '', 'images': images, 'inline_hashes': inline_hashes}),
              'ticker': None, 'market': None, 'file_sha256': None,
              'identity_status': 'not_verified', 'quality_status': 'metadata_only',
              'training_eligible': False, 'rights_status': 'pdf_permission_required'}
    record['metadata_sha256'] = digest(record)
    return record


def metadata_run(state_store, policy, max_posts=350, max_pages=40, max_requests=450, batch=10):
    require_permission(policy, 'metadata')
    state = state_store.load()
    state.setdefault('reports', {}); state.setdefault('history', []); state.setdefault('seen_urls', {})
    state.setdefault('tombstones', []); state.setdefault('errors', [])
    client = BoundedClient(max_requests=max_requests)
    robots = client.check_robots()
    terms = BeautifulSoup(client.get(BASE + '/service/agreement'), 'html.parser').select_one('#content')
    if not terms or digest(terms.get_text(' ', strip=True).encode()) != policy.get('agreement_text_sha256'):
        raise PermissionError('source_terms_changed_review_required')
    first = client.get(BOARD); listed, total_pages, total_count = parse_listing(first)
    if not listed: raise RuntimeError('listing_layout_changed')
    if state.get('pending_urls'):
        priority = [r['post_url'] for r in listed if r['report_id'] not in state['reports'] or
                    state['reports'][r['report_id']]['title'] != r['title']]
        state['pending_urls'] = list(dict.fromkeys(priority + state['pending_urls']))
    # Complete an interrupted bounded queue before starting a new snapshot.
    if not state.get('pending_urls'):
        urls = [r['post_url'] for r in listed]
        for page in range(2, min(total_pages, max_pages) + 1):
            more, _, _ = parse_listing(client.get(BOARD + '&per_page=' + str(page)))
            urls += [r['post_url'] for r in more]
        state['pending_urls'] = list(dict.fromkeys(urls))
        state['scan_started_at'] = now(); state['scan_urls'] = state['pending_urls'].copy()
        state['scan_listing_complete'] = total_pages <= max_pages
        state_store.save(state)
    successes = changes = failures = 0
    while state['pending_urls'] and successes + failures < max_posts:
        url = state['pending_urls'][0]
        try:
            record = parse_post(client.get(url), url)
            checked = now(); old = state['reports'].get(record['report_id'])
            record['first_collected_at'] = old['first_collected_at'] if old else checked
            record['last_checked_at'] = checked
            record['metadata_version'] = (old['metadata_version'] if old else 0)
            changed = not old or old['metadata_sha256'] != record['metadata_sha256']
            if changed:
                if old: state['history'].append(old)
                record['metadata_version'] += 1; changes += 1
            record['version_first_seen_at'] = checked if changed else old['version_first_seen_at']
            record['modified_detected_at'] = checked if changed and old else (old.get('modified_detected_at') if old else None)
            # No archived-version proof: never backdate the currently observed version to the posting date.
            record['available_not_before'] = record['version_first_seen_at']
            record['available_at'] = None  # Resolved only against a verified trading calendar.
            record['availability_rule'] = 'next_verified_trading_session_after_version_first_seen_KST'
            state['reports'][record['report_id']] = record; state['seen_urls'][url] = checked
            successes += 1
            emit('post_complete', report_id=record['report_id'], changed=changed)
        except (RuntimeError, ValueError) as e:
            code = str(e) if re.fullmatch(r'[a-zA-Z0-9_:]+', str(e)) else type(e).__name__
            state['errors'].append({'url': url, 'at': now(), 'code': code}); failures += 1
            if 'budget' in code:
                state_store.save(state); break  # Keep uncompleted URL at the front for resume.
            # Failed URLs are retried in the next scan, not an unbounded loop in this run.
        state['pending_urls'].pop(0)
        if (successes + failures) % batch == 0: state_store.save(state)
    if not state['pending_urls']:
        if state['scan_listing_complete']:
            current = set(state['scan_urls'])
            for url in state['seen_urls']:
                if url not in current and not any(x['url'] == url for x in state['tombstones']):
                    state['tombstones'].append({'url': url, 'noticed_at': now(), 'reason': 'missing_from_complete_listing'})
        state['scan_completed_at'] = now()
    state['last_run_at'] = now(); state['errors'] = state['errors'][-1000:]
    state_store.save(state)
    return state, {'kind': 'metadata', 'successes': successes, 'changed': changes, 'failures': failures,
                   'coverage_status': 'partial' if state['pending_urls'] else 'scan_complete',
                   'source_requests': client.requests, 'source_bytes': client.bytes,
                   'pending': len(state['pending_urls']), 'listed_total': total_count,
                   'listing_pages': total_pages, 'robots': robots, 'receipts': client.receipts,
                   'completed_at': now()}
