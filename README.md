# ctfd-downloader

Script to download all challenges from a CTFd server

## Usage

```text
usage: down.py [-h] -u URL (-t TOKEN | -c COOKIE) [-o OUTPUT]

CTFd Downloader

options:
  -h, --help            show this help message and exit
  -u URL, --url URL     CTFd URL
  -t TOKEN, --token TOKEN
                        CTFd API Token
  -c COOKIE, --cookie COOKIE
                        CTFd Session Cookie
  -o OUTPUT, --output OUTPUT
                        Output directory
```

Example

```text
python3 down.py -u demo.ctfd.io -t <token> -o /tmp/ctfd
```
