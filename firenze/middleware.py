from ipaddress import ip_address, ip_network

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class InternalOnlyMiddleware(BaseHTTPMiddleware):
    """Reject requests to ``path_prefix`` whose TCP peer is not in ``allowed_networks``.

    Compares ``request.client.host`` against CIDR blocks. Intended for routes
    that are only ever called by local processes (e.g. Asterisk hitting the
    AGI endpoints on the same host or private interface).

    Note: if a reverse proxy is placed in front of the protected prefix, the
    peer address becomes the proxy's address. In that case switch to an
    X-Forwarded-For-aware check and pin the trusted proxy IP.
    """

    def __init__(self, app, *, path_prefix: str, allowed_networks: list[str]):
        super().__init__(app)
        self.prefix = path_prefix
        self.networks = [ip_network(n) for n in allowed_networks]

    async def dispatch(self, request, call_next):
        if request.url.path.startswith(self.prefix):
            peer = request.client.host if request.client else None
            if not peer or not self._allowed(peer):
                return PlainTextResponse("Forbidden", status_code=403)
        return await call_next(request)

    def _allowed(self, peer: str) -> bool:
        try:
            addr = ip_address(peer)
        except ValueError:
            return False
        return any(addr in net for net in self.networks)
