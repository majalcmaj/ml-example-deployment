from urllib3.util import Retry
from requests import Response, Session
from requests.adapters import HTTPAdapter

from config import CONFIG


class TimeoutSession(Session):
    def request(self, *arg, **kwargs) -> Response:
        kwargs.setdefault("timeout", CONFIG.request_timeout_s)
        return super().request(*arg, **kwargs)


http = TimeoutSession()
_retries = Retry(
    total=3,
    backoff_factor=1,
    backoff_jitter=1,
    status_forcelist=[408, 429, 500, 502, 503, 504],
)
http.mount("https://", HTTPAdapter(max_retries=_retries))
http.mount("http://", HTTPAdapter(max_retries=_retries))
