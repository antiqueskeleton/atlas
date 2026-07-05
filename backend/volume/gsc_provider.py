from datetime import date, timedelta

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from backend.volume.base_volume_provider import VolumeProvider

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"


class GoogleSearchConsoleProvider(VolumeProvider):
    """
    Real search-query volume via the Google Search Console Search Analytics
    API. Auth is a service-account JSON key file (self.credential) that has
    been added as a user on the target property in Search Console — no
    browser OAuth consent flow needed, works unattended (the standard
    approach for a backend/desktop app, as opposed to a per-user OAuth flow
    which would need a local redirect server and refresh-token management).
    """
    provider_name = "Google Search Console"

    def get_query_volumes(self, days: int = 90) -> dict:
        if not self.credential:
            return {"queries": [], "error": "No service-account credential configured."}
        if not self.site_url:
            return {"queries": [], "error": "No site URL configured."}

        try:
            token = self._get_access_token()
        except Exception as exc:
            return {"queries": [], "error": f"Authentication failed: {exc}"}

        end = date.today()
        start = end - timedelta(days=days)
        url = _SEARCH_ANALYTICS_URL.format(site=requests.utils.quote(self.site_url, safe=""))
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 1000,
        }
        try:
            resp = requests.post(
                url, json=body,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
        except Exception as exc:
            return {"queries": [], "error": str(exc)[:200]}

        if resp.status_code >= 400:
            return {"queries": [], "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

        data = resp.json()
        queries = [
            {
                "query": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
            }
            for row in data.get("rows", [])
            if row.get("keys")
        ]
        return {"queries": queries, "error": ""}

    def _get_access_token(self) -> str:
        creds = service_account.Credentials.from_service_account_file(
            self.credential, scopes=_SCOPES,
        )
        creds.refresh(Request())
        return creds.token
