from urllib3.util import Retry
from requests import Response, Session
from requests.adapters import HTTPAdapter


class TimeoutSession(Session):
    def request(self, *arg, **kwargs) -> Response:
        kwargs.setdefault("timeout", 30)
        return super().request(*arg, **kwargs)


def create_http_session(correlation_id: str) -> Session:
    http = TimeoutSession()
    _retries = Retry(
        total=3,
        backoff_factor=1,
        backoff_jitter=1,
        status_forcelist=[408, 429, 500, 502, 503, 504],
    )
    http.headers.update({"X-Correlation-ID": correlation_id})
    http.mount("https://", HTTPAdapter(max_retries=_retries))
    http.mount("http://", HTTPAdapter(max_retries=_retries))
    return http
