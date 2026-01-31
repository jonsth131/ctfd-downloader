#!/usr/bin/env python3
"""
CTFd downloader CLI tool.
"""
import requests
import argparse
import os
import re
import sys
import logging
import concurrent.futures
from hashlib import md5


CHALLENGES_PATH = '/api/v1/challenges'
CHALLENGE_PATH = '/api/v1/challenges/{}'

CYAN = '\033[96m'
RED = '\033[91m'
GREEN = '\033[92m'
END = '\033[0m'


logger = logging.getLogger(__name__)


def spinning_cursor():
    """Yield an infinite spinner sequence of characters.

    Useful for showing progress in the terminal one character at a time.
    """
    while True:
        for cursor in '|/-\\':
            yield cursor


def clean_name(name):
    """Normalize a challenge or category name into a filesystem-safe slug.

    Rules:
    - lowercases the string
    - collapses whitespace to hyphens
    - removes any characters other than a-z, 0-9 and hyphen
    - collapses multiple hyphens and trims leading/trailing hyphens
    - if the result is empty, produces 'unnamed-<8-hex>' based on md5

    Returns the normalized slug as a string.
    """

    original_name = name or ''
    s = (name or '').lower()
    s = re.sub(r'\s+', '-', s)
    s = re.sub(r'[^a-z0-9-]+', '', s)
    s = re.sub(r'-+', '-', s).strip('-')

    if not s:
        s = 'unnamed-' + md5(original_name.encode()).hexdigest()[:8]

    return s


def build_session(token, cookie):
    """Create and configure a `requests.Session`.

    Sets JSON content-type header and, if provided, attaches an
    Authorization token header or a session cookie.

    Returns the configured `requests.Session` object.
    """

    s = requests.Session()
    if token:
        s.headers.update({'Authorization': f'Token {token}'})
    if cookie:
        s.cookies.update({'session': cookie})
    s.headers.update({'Content-Type': 'application/json'})
    return s


def fetch_challenges(s, url):
    """Fetch the list of challenges from the CTFd API.

    Returns the parsed list (`r.json()['data']`) on success, or `None`
    on network or parsing errors. Network errors are logged.
    """
    try:
        with s.get(url + CHALLENGES_PATH, timeout=10) as r:
            if r.status_code != 200:
                logger.error('Error fetching challenges: %s', r.status_code)
                return None
            try:
                return r.json()['data']
            except Exception:
                logger.error(f'{RED}[!] Error parsing challenges{END}')
                logger.debug(r.text)
                return None
    except requests.exceptions.RequestException as e:
        logger.error(f'{RED}Request error fetching challenges: {e}{END}')
        return None


def fetch_challenge_data(s, url, challenge_id):
    """Fetch detailed data for a single challenge by id.

    Returns the `data` mapping on success, or `None` on error.
    """
    try:
        with s.get(url + CHALLENGE_PATH.format(challenge_id), timeout=10) as r:
            if r.status_code != 200:
                logger.error(
                    f'{RED}Error fetching challenge {challenge_id}{END}')
                return None
            try:
                return r.json()['data']
            except Exception:
                logger.error(
                    f'{RED}[!] Error parsing challenge {challenge_id}{END}')
                logger.debug(r.text)
                return None
    except requests.exceptions.RequestException as e:
        logger.error(
            f'{RED}Request error fetching challenge {challenge_id}: {e}{END}')
        return None


def save_description(dest_dir, description):
    """Write the challenge description string to `description.md`.
    """
    with open(os.path.join(dest_dir, 'description.md'), 'w') as f:
        f.write(description)


def download_files(s, base_url, files, dest_dir, max_workers=4, show_spinner=True):
    """Download a list of files, optionally concurrently.

    Parameters
    - s: requests.Session to use for requests
    - base_url: base URL to prepend to each file path
    - files: iterable of file path strings (each typically begins with `/`)
    - dest_dir: directory to write files into
    - max_workers: number of threads to use; if <=1 downloads are sequential
    - show_spinner: when True prints spinner characters during downloads

    Returns True if all downloads succeeded, False if any failed.
    """
    spinner = spinning_cursor()

    def _download_single(file):
        file_url = base_url + file
        file_name = file.split('/')[-1].split('?')[0]
        file_path = os.path.join(dest_dir, file_name)
        try:
            with s.get(file_url, stream=True, timeout=10) as r:
                if r.status_code != 200:
                    logger.error('Error downloading %s: %s',
                                 file_url, r.status_code)
                    return False
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            if show_spinner:
                                print(next(spinner), end='', flush=True)
                                print('\b', end='', flush=True)
                        f.write(chunk)
            return True
        except requests.exceptions.RequestException as e:
            logger.error('Request error downloading %s: %s', file_url, e)
            return False

    success = True
    if max_workers and max_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_download_single, f) for f in files]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    ok = fut.result()
                    if not ok:
                        success = False
                except Exception as e:
                    logger.error('Download task raised: %s', e)
                    success = False
    else:
        for f in files:
            ok = _download_single(f)
            if not ok:
                success = False

    return success


def main(url, token, cookie, output, show_spinner=True):
    """Run the downloader workflow and return an exit code.

    Returns 0 on success and 1 if any fetch or download failed.
    """
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if url.endswith('/'):
        url = url[:-1]
    s = build_session(token, cookie)

    os.makedirs(output, exist_ok=True)

    challenges = fetch_challenges(s, url)
    if challenges is None:
        return 1

    failure = False

    logger.info(f'{GREEN}[+] Found {len(challenges)} challenges{END}')

    for challenge in challenges:
        challenge_id = challenge['id']
        challenge_name = challenge['name']
        challenge_category = challenge['category']

        challenge_name_dir = clean_name(challenge_name)
        challenge_category_dir = clean_name(challenge_category)
        challenge_output = os.path.join(
            output, challenge_category_dir, challenge_name_dir)
        os.makedirs(challenge_output, exist_ok=True)

        print(f'Downloading {challenge_name} ({challenge_category})', end=' ')

        if os.path.exists(os.path.join(challenge_output, 'description.md')):
            print('... Skipping, already downloaded')
            continue

        challenge_data = fetch_challenge_data(s, url, challenge_id)
        if challenge_data is None:
            failure = True
            continue

        description = challenge_data['description']
        files = challenge_data['files']

        save_description(challenge_output, description)
        ok = download_files(s, url, files, challenge_output,
                            show_spinner=show_spinner)
        if not ok:
            failure = True

        print(f'{GREEN}Done{END}')

    return 1 if failure else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    parser = argparse.ArgumentParser(description='CTFd Downloader')
    parser.add_argument('-u', '--url', type=str,
                        help='CTFd URL', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--token', type=str, help='CTFd API Token')
    group.add_argument('-c', '--cookie', type=str, help='CTFd Session Cookie')
    parser.add_argument('-o', '--output', type=str,
                        help='Output directory', required=False, default='.')
    parser.add_argument('--no-spinner', action='store_true',
                        help='Disable spinner output')

    args = parser.parse_args()

    rc = main(args.url, args.token, args.cookie,
              args.output, show_spinner=not args.no_spinner)
    sys.exit(rc if rc is not None else 0)
