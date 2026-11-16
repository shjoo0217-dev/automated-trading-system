from __future__ import annotations
import base64, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def dump(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def emit(event, **data):
    # Only explicit, nonsecret fields. Never print request objects, headers or exception bodies.
    print(json.dumps({'at': now(), 'event': event, **data}, ensure_ascii=False), flush=True)


class LocalState:
    """Remote workspace pilot/test only; never advertised as persistent deployment."""
    def __init__(self, path): self.path = Path(path)
    def load(self): return json.loads(self.path.read_text()) if self.path.exists() else {}
    def save(self, value):
        tmp = self.path.with_suffix('.tmp'); dump(tmp, value); tmp.replace(self.path)


class GitHubState:
    """Durable checkpoint branch with optimistic concurrency, using an ephemeral job token."""
    def __init__(self, repo, branch='star-state', path='checkpoint.json'):
        self.repo, self.branch, self.path, self.sha = repo, branch, path, None
        self.session = requests.Session()
        self.session.headers.update({'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                                     'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'})
        self.base = 'https://api.github.com/repos/' + repo
    def request(self, method, endpoint, **kwargs):
        for attempt in range(3):
            r = self.session.request(method, self.base + endpoint, timeout=40, **kwargs)
            if r.status_code not in (429, 500, 502, 503, 504): return r
            time.sleep(min(30, 2 ** (attempt + 1)))
        raise RuntimeError('github_transient_failure')
    def load(self):
        r = self.request('GET', '/contents/' + self.path, params={'ref': self.branch})
        if r.status_code == 404: return {}
        if r.status_code != 200: raise RuntimeError('github_state_read_' + str(r.status_code))
        obj = r.json(); self.sha = obj['sha']
        if obj.get('encoding') == 'base64' and obj.get('content'):
            return json.loads(base64.b64decode(obj['content']))
        r = self.request('GET', '/contents/' + self.path, params={'ref': self.branch},
                         headers={'Accept': 'application/vnd.github.raw+json'})
        if r.status_code != 200: raise RuntimeError('github_state_raw_read_failed')
        return r.json()
    def save(self, value):
        body = {'message': 'STAR checkpoint [skip ci]', 'branch': self.branch,
                'content': base64.b64encode(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()).decode()}
        if self.sha: body['sha'] = self.sha
        r = self.request('PUT', '/contents/' + self.path, json=body)
        if r.status_code not in (200, 201):
            # A conflict must stop the job; never overwrite someone else's checkpoint.
            raise RuntimeError('github_checkpoint_write_' + str(r.status_code))
        self.sha = r.json()['content']['sha']


def require_permission(policy, action):
    grant = policy.get('permissions', {}).get(action, {})
    if not (grant.get('allowed') is True and grant.get('evidence')):
        raise PermissionError('source_permission_missing:' + action)
    expiry = grant.get('valid_until')
    if expiry and now() > expiry: raise PermissionError('source_permission_expired:' + action)
