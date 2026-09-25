from __future__ import annotations

import ipaddress
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..canonical import sha256_bytes
from ..model import Acquisition, SourceRef, UrlSource, now_iso
from ..policy import IngestPolicy
from .base import AcquisitionFailed, PolicyRejected


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _host_is_forbidden(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise AcquisitionFailed(f"DNS resolution failed for {host}") from exc
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _safe_url_provenance(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError as exc:
        raise PolicyRejected("URL contains an invalid port") from exc
    netloc = host + (f":{port}" if port is not None else "")
    locator = parsed._replace(netloc=netloc, query="", fragment="").geturl()
    return locator, sha256_bytes(url.encode("utf-8"))


class HttpAdapter:
    name = "http"
    version = "1"

    def __init__(self, opener=None):
        self.opener = opener or build_opener(_NoRedirect())

    def supports(self, source) -> bool:
        return isinstance(source, UrlSource)

    @staticmethod
    def _check_url(url: str, policy: IngestPolicy) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"}:
            raise PolicyRejected("URL scheme must be http or https")
        if parsed.scheme == "http" and not policy.allow_http:
            raise PolicyRejected("plain HTTP is disabled by policy")
        if not parsed.hostname:
            raise PolicyRejected("URL must include a host")
        if policy.deny_private_networks and _host_is_forbidden(parsed.hostname):
            raise PolicyRejected("private/loopback/link-local destination denied")

    def acquire(self, source: UrlSource, policy: IngestPolicy) -> Acquisition:
        current = source.url
        redirects = 0
        while True:
            self._check_url(current, policy)
            request = Request(current, headers={"User-Agent": "vera-ingest/0.1"})
            try:
                response = self.opener.open(request, timeout=policy.timeout_seconds)
            except HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308} and exc.headers.get("Location"):
                    if redirects >= policy.max_redirects:
                        raise PolicyRejected("redirect limit exceeded") from exc
                    current = urljoin(current, exc.headers["Location"])
                    redirects += 1
                    continue
                raise AcquisitionFailed(f"HTTP error {exc.code}") from exc
            except URLError as exc:
                raise AcquisitionFailed(f"HTTP acquisition failed: {exc.reason}") from exc
            with response:
                data = response.read(policy.max_bytes + 1)
                if len(data) > policy.max_bytes:
                    raise PolicyRejected(f"response exceeds max_bytes={policy.max_bytes}")
                final_url = response.geturl()
                self._check_url(final_url, policy)
                content_type = response.headers.get("Content-Type")
                status = getattr(response, "status", None)
            final_locator, final_url_sha256 = _safe_url_provenance(final_url)
            _, requested_url_sha256 = _safe_url_provenance(source.url)
            return Acquisition(
                data=data,
                source=SourceRef(
                    scheme=urlparse(final_url).scheme,
                    locator=final_locator,
                    adapter=self.name,
                    adapter_version=self.version,
                    observed_at=now_iso(),
                    source_identity={
                        "url_locator": final_locator,
                        "url_sha256": final_url_sha256,
                    },
                    claimed_metadata={"requested_url_sha256": requested_url_sha256},
                    observed_metadata={"status": status, "redirects": redirects},
                ),
                claimed_media_type=content_type,
            )
