import requests
from decouple import config

GITHUB_TOKEN = config('GITHUB_ACCESS_TOKEN', default='')


def fetch_repo_meta(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}'
    headers = {}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    return {
        'stars': data.get('stargazers_count', 0),
        'forks': data.get('forks_count', 0),
        'primary_language': data.get('language') or '',
        'last_commit_at': data.get('pushed_at'),
    }
def fetch_repo_readme(owner, repo):
    url = f'https://api.github.com/repos/{owner}/{repo}/readme'
    headers = {'Accept': 'application/vnd.github.raw+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 404:
        return ''
    response.raise_for_status()
    return response.text


SOURCE_EXT_LANG = {
    'py': 'python', 'js': 'javascript', 'jsx': 'jsx', 'ts': 'typescript', 'tsx': 'tsx',
    'html': 'html', 'css': 'css', 'scss': 'scss', 'json': 'json',
    'java': 'java', 'c': 'c', 'cpp': 'cpp', 'h': 'c', 'cs': 'csharp', 'go': 'go',
    'rs': 'rust', 'php': 'php', 'rb': 'ruby', 'kt': 'kotlin', 'swift': 'swift',
    'sql': 'sql', 'sh': 'bash', 'yml': 'yaml', 'yaml': 'yaml', 'vue': 'vue', 'dart': 'dart',
}
SOURCE_SKIP_DIRS = {
    'node_modules', 'dist', 'build', 'vendor', '.git', 'venv', '__pycache__',
    'migrations', 'static', 'staticfiles', '.next', 'coverage',
}
SOURCE_SKIP_NAMES = {'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock'}


def fetch_repo_source(owner, repo, max_files=12, max_chars=20000):
    """Repo ki chhoti source files (text) fetch karta hai. [(path, language, content)]"""
    headers = {'Accept': 'application/vnd.github+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    tree_resp = requests.get(
        f'https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1',
        headers=headers, timeout=15,
    )
    tree_resp.raise_for_status()
    tree = tree_resp.json().get('tree', [])

    candidates = []
    for item in tree:
        if item.get('type') != 'blob':
            continue
        path = item['path']
        segments = path.lower().split('/')
        if any(seg in SOURCE_SKIP_DIRS for seg in segments[:-1]):
            continue
        name = segments[-1]
        if name in SOURCE_SKIP_NAMES or name.endswith('.min.js'):
            continue
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        if ext not in SOURCE_EXT_LANG:
            continue
        size = item.get('size') or 0
        if size == 0 or size > max_chars:
            continue
        candidates.append((path.count('/'), path, SOURCE_EXT_LANG[ext]))

    candidates.sort()
    raw_headers = {'Accept': 'application/vnd.github.raw+json'}
    if GITHUB_TOKEN:
        raw_headers['Authorization'] = f'token {GITHUB_TOKEN}'

    files = []
    for _, path, lang in candidates[:max_files]:
        r = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/contents/{path}',
            headers=raw_headers, timeout=15,
        )
        if r.status_code != 200:
            continue
        text = r.text[:max_chars]
        if text.strip():
            files.append((path, lang, text))
    return files
