# ctfd-downloader

Script to download all challenges from a CTFd server

## Usage

```text
usage: down.py [-h] -u URL (-t TOKEN | -c COOKIE) [-o OUTPUT] [--no-spinner]

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
  --no-spinner          Disable spinner output
```

Example

```text
python3 down.py -u demo.ctfd.io -t <token> -o /tmp/ctfd
python3 down.py -u demo.ctfd.io -t <token> -o /tmp/ctfd --no-spinner
```
