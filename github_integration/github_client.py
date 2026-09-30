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