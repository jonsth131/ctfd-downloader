#!/usr/bin/env python3
import requests
import argparse
import os
import string
from hashlib import md5


CHALLENGES_PATH = '/api/v1/challenges'
CHALLENGE_PATH = '/api/v1/challenges/{}'

CYAN = '\033[96m'
RED = '\033[91m'
GREEN = '\033[92m'
END = '\033[0m'


def spinning_cursor():
    while True:
        for cursor in '|/-\\':
            yield cursor


def clean_name(name):
    original_name = name
    name = name.replace(' ', '-').lower()
    valid = string.ascii_lowercase + string.digits + '-'
    name = ''.join(c for c in name if c in valid)
    while name.startswith('-'):
        name = name[1:]

    name = name.replace('--', '-')

    if name == '':
        name = 'unnamed-' + md5(original_name.encode()).hexdigest()[:8]

    return name


def main(url, token, cookie, output):
    if url.endswith('/'):
        url = url[:-1]

    s = requests.Session()

    if token:
        s.headers.update({'Authorization': f'Token {token}'})

    if cookie:
        cookies = {
            'session': cookie
        }
        s.cookies.update(cookies)

    s.headers.update({'Content-Type': 'application/json'})

    os.makedirs(output, exist_ok=True)

    with s.get(url + CHALLENGES_PATH) as r:
        if r.status_code != 200:
            print('Error fetching challenges')
            return

        try:
            challenges = r.json()['data']
        except:
            print(f'{RED}[!] Error parsing challenges{END}')
            print(r.text)
            return

    print(f'{GREEN}[+] Found {len(challenges)} challenges{END}')

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

        with s.get(url + CHALLENGE_PATH.format(challenge_id)) as r:
            if r.status_code != 200:
                print(f'{RED}Error fetching challenge {challenge_id}{END}')
                continue

            challenge_data = r.json()['data']

        description = challenge_data['description']
        files = challenge_data['files']

        with open(os.path.join(challenge_output, 'description.md'), 'w') as f:
            f.write(description)

        spinner = spinning_cursor()
        for file in files:
            file_url = url + file
            file_name = file.split('/')[-1].split('?')[0]
            file_path = os.path.join(challenge_output, file_name)

            with s.get(file_url, stream=True) as r:
                with open(file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            print(next(spinner), end='', flush=True)
                            print('\b', end='', flush=True)
                        f.write(chunk)

        print(f'{GREEN}Done{END}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CTFd Downloader')
    parser.add_argument('-u', '--url', type=str,
                        help='CTFd URL', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--token', type=str, help='CTFd API Token')
    group.add_argument('-c', '--cookie', type=str, help='CTFd Session Cookie')
    parser.add_argument('-o', '--output', type=str,
                        help='Output directory', required=False, default='.')

    args = parser.parse_args()

    main(args.url, args.token, args.cookie, args.output)
