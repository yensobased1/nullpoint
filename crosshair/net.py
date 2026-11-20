"""The only way Nullpoint talks to the internet: HTTPS GET to a short list of GitHub hosts.

Certificates are checked (default SSL context), redirects may only go to the same list, every request has a
timeout and every response a size limit. Anything else raises NetError.
"""
import ssl
import urllib.request
from urllib.parse import urlsplit

ALLOWED_HOSTS = {"github.com", "api.github.com", "objects.githubusercontent.com", "raw.githubusercontent.com"}
TIMEOUT = 8  # seconds


class NetError(OSError):
    pass


def check_url(url):
    u = urlsplit(url)
    if u.scheme != "https" or (u.hostname or "").lower() not in ALLOWED_HOSTS or u.username or u.password:
        raise NetError(f"blocked URL: {u.scheme}://{u.hostname}")
    return url


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_CheckedRedirects, urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def get(url, max_bytes, headers=None):
    """-> response body (bytes). Raises NetError for blocked URLs / too-big answers, OSError for network errors."""
    req = urllib.request.Request(check_url(url), headers={"User-Agent": "Nullpoint", **(headers or {})})
    with _opener.open(req, timeout=TIMEOUT) as r:  # nosec B310 - scheme and host are checked above (https only)
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise NetError("response too big")
    return data
