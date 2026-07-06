"""
Tests for backend/targeted_review/ (#25) — providers' parsing exercised
against canned API payloads / page HTML (never live HTTP), repository
against a tmp-path database, and the service's gap analysis against seeded
snapshots.
"""
from unittest.mock import patch, MagicMock

from backend.targeted_review import targeted_review_service as trs
from backend.targeted_review.editorial_search_provider import (
    EditorialSearchProvider, parse_editorial_results,
)
from backend.targeted_review.reddit_provider import (
    RedditPlatformProvider, parse_reddit_results,
)
from backend.targeted_review.retailer_provider import parse_listing_html
from backend.targeted_review.targeted_review_repository import TargetedReviewRepository
from backend.targeted_review.targeted_review_service import TargetedReviewService
from backend.targeted_review.youtube_provider import (
    YouTubePlatformProvider, parse_youtube_results,
)


class FakeConfig:
    def __init__(self, creds: dict | None = None):
        self._creds = creds or {}

    def get_platform_credential(self, platform, field):
        return self._creds.get((platform, field), "")


# ── YouTube provider ──────────────────────────────────────────────────────────

_YT_SEARCH = {
    "pageInfo": {"totalResults": 4321},
    "items": [
        {"id": {"videoId": "abc"}, "snippet": {"title": "Firman W03083 review",
         "channelTitle": "Generatorist", "publishedAt": "2026-01-15T00:00:00Z"}},
        {"id": {"videoId": "def"}, "snippet": {"title": "Firman vs Champion",
         "channelTitle": "ToolGuy", "publishedAt": "2025-11-02T00:00:00Z"}},
    ],
}
_YT_STATS = {"abc": {"viewCount": "150000"}, "def": {"viewCount": "980000"}}


def test_youtube_no_key_returns_in_band_error():
    provider = YouTubePlatformProvider()
    result = provider.fetch_brand_presence("Firman")
    assert "No YouTube API key" in result["error"]
    assert result["brand"] == "Firman"


def test_youtube_parse_sorts_top_videos_by_views_and_totals():
    parsed = parse_youtube_results(_YT_SEARCH, recent_total=87, stats_by_id=_YT_STATS)
    assert parsed["video_results"] == 4321
    assert parsed["recent_videos_365d"] == 87
    assert parsed["top_videos"][0]["video_id"] == "def"  # 980k sorts above 150k
    assert parsed["top_videos_total_views"] == 1_130_000


def test_youtube_api_error_reported_in_band():
    provider = YouTubePlatformProvider()
    provider.set_credentials({"api_key": "k"})
    bad = MagicMock(status_code=403)
    bad.json.return_value = {"error": {"message": "quotaExceeded"}}
    with patch("backend.targeted_review.youtube_provider.requests.get", return_value=bad):
        result = provider.fetch_brand_presence("Firman")
    assert "quotaExceeded" in result["error"]


# ── Reddit provider ───────────────────────────────────────────────────────────

_REDDIT_SEARCH = {"data": {"children": [
    {"kind": "t3", "data": {"title": "Firman W03083 after 2 years", "subreddit":
     "Generators", "score": 250, "num_comments": 40, "created_utc": 1750000000}},
    {"kind": "t3", "data": {"title": "Firman tri-fuel worth it?", "subreddit":
     "preppers", "score": 90, "num_comments": 15, "created_utc": 1750100000}},
    {"kind": "t3", "data": {"title": "Generator advice", "subreddit":
     "Generators", "score": 10, "num_comments": 5, "created_utc": 1750200000}},
]}}


def test_reddit_no_credentials_returns_in_band_error():
    result = RedditPlatformProvider().fetch_brand_presence("Firman")
    assert "not configured" in result["error"]


def test_reddit_parse_counts_engagement_and_subreddits():
    parsed = parse_reddit_results(_REDDIT_SEARCH)
    assert parsed["posts_last_year"] == 3
    assert parsed["posts_capped"] is False
    assert parsed["total_score"] == 350
    assert parsed["total_comments"] == 60
    assert parsed["top_subreddits"][0] == ("Generators", 2)
    assert parsed["top_posts"][0]["score"] == 250  # sorted by score desc


def test_reddit_auth_failure_reported_in_band():
    provider = RedditPlatformProvider()
    provider.set_credentials({"client_id": "id", "client_secret": "secret"})
    bad = MagicMock(status_code=401)
    with patch("backend.targeted_review.reddit_provider.requests.post", return_value=bad):
        result = provider.fetch_brand_presence("Firman")
    assert "Reddit auth failed" in result["error"]


# ── Editorial search provider ─────────────────────────────────────────────────

def _editorial_payload(total, title="", link=""):
    payload = {"searchInformation": {"totalResults": str(total)}}
    if title:
        payload["items"] = [{"title": title, "link": link}]
    return payload


def test_editorial_no_credentials_returns_in_band_error():
    result = EditorialSearchProvider().fetch_brand_presence("Firman")
    assert "not configured" in result["error"]


def test_editorial_parse_counts_coverage_and_strongest_site():
    parsed = parse_editorial_results([
        ("Consumer Reports", "consumerreports.org", _editorial_payload(0)),
        ("CNET", "cnet.com", _editorial_payload(42, "Best generators", "https://cnet.com/x")),
        ("Bob Vila", "bobvila.com", _editorial_payload(7, "Firman review", "https://bobvila.com/y")),
    ])
    assert parsed["sites_with_coverage"] == 2
    assert parsed["sites_checked"] == 3
    assert parsed["total_results"] == 49
    assert parsed["strongest_site"] == "CNET"
    assert parsed["per_site"][1]["top_title"] == "Best generators"


def test_editorial_api_error_aborts_brand_in_band():
    """Quota exhaustion mid-run must NOT produce a silently-undercounted
    brand that gap analysis then misreads as a real gap."""
    provider = EditorialSearchProvider()
    provider.set_credentials({"api_key": "k", "engine_id": "cx"})
    bad = MagicMock(status_code=429)
    bad.json.return_value = {"error": {"message": "Quota exceeded"}}
    with patch("backend.targeted_review.editorial_search_provider.requests.get",
               return_value=bad):
        result = provider.fetch_brand_presence("Firman")
    assert "Quota exceeded" in result["error"]


def test_gap_analysis_flags_editorial_coverage_gap(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    repo.save_findings("Editorial Coverage", [
        {"brand": "Firman", "platform": "Editorial Coverage",
         "sites_with_coverage": 1, "sites_checked": 6, "total_results": 12,
         "strongest_site": "Bob Vila", "error": ""},
        {"brand": "Honda", "platform": "Editorial Coverage",
         "sites_with_coverage": 6, "sites_checked": 6, "total_results": 800,
         "strongest_site": "CNET", "error": ""},
    ])
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("editorial")
    sites_gap = next(f for f in findings if "sites covering" in f["metric_label"].lower())
    assert sites_gap["type"] == "gap"
    assert sites_gap["leader_brand"] == "Honda"
    assert "of 6 sites" in sites_gap["target_display"]
    assert any("roundup" in t for t in sites_gap["tactics"])


# ── Retailer listing parsing ──────────────────────────────────────────────────

_JSONLD_HTML = """
<html><head><script type="application/ld+json">
{"@type": "Product", "name": "FIRMAN 4550W Generator",
 "aggregateRating": {"ratingValue": "4.5", "reviewCount": "1234"},
 "offers": {"price": "499.00"}}
</script></head><body></body></html>
"""

_AMAZON_HTML = """
<html><body>
<span id="productTitle">FIRMAN W03083 Generator</span>
<span id="acrPopover" title="4.6 out of 5 stars"></span>
<span id="acrCustomerReviewText">12,345 ratings</span>
<span class="a-offscreen">$449.99</span>
</body></html>
"""


def test_parse_listing_jsonld_extracts_rating_reviews_price():
    result = parse_listing_html(_JSONLD_HTML, "https://www.homedepot.com/p/x")
    assert result["rating"] == 4.5
    assert result["review_count"] == 1234
    assert result["price"] == 499.0
    assert result["retailer"] == "Home Depot"
    assert result["error"] == ""


def test_parse_listing_amazon_selectors_extract_data():
    result = parse_listing_html(_AMAZON_HTML, "https://www.amazon.com/dp/X")
    assert result["rating"] == 4.6
    assert result["review_count"] == 12345
    assert result["price"] == 449.99
    assert result["retailer"] == "Amazon"


def test_parse_listing_without_review_data_reports_in_band():
    result = parse_listing_html("<html><body>nothing</body></html>",
                                "https://www.lowes.com/pd/x")
    assert result["rating"] is None
    assert "No rating/review data" in result["error"]


# ── Repository ────────────────────────────────────────────────────────────────

def test_repository_latest_findings_returns_newest_snapshot_per_brand(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    repo.save_findings("YouTube", [{"brand": "Firman", "video_results": 10}],
                       collected_at="2026-07-01T00:00:00")
    repo.save_findings("YouTube", [{"brand": "Firman", "video_results": 99},
                                   {"brand": "Honda", "video_results": 500}],
                       collected_at="2026-07-06T00:00:00")
    latest = repo.latest_findings("YouTube")
    assert latest["Firman"]["video_results"] == 99  # newest wins
    assert latest["Honda"]["video_results"] == 500
    assert latest["Firman"]["collected_at"] == "2026-07-06T00:00:00"


def test_repository_url_crud_and_duplicate_rejection(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    assert repo.add_product_url("Firman", "https://amazon.com/dp/1") is True
    assert repo.add_product_url("Firman", "https://amazon.com/dp/1") is False
    repo.add_product_url("Honda", "https://amazon.com/dp/2")
    rows = repo.list_product_urls()
    assert len(rows) == 2
    repo.delete_product_url(rows[0][0])
    assert len(repo.list_product_urls()) == 1


# ── Service: collection ───────────────────────────────────────────────────────

class _FakeYouTube(YouTubePlatformProvider):
    def fetch_brand_presence(self, brand):
        return {"brand": brand, "platform": "YouTube",
                "video_results": {"Firman": 100, "Honda": 900}.get(brand, 0),
                "recent_videos_365d": 5, "top_videos": [],
                "top_videos_total_views": 0, "error": ""}


def test_collect_platform_persists_one_snapshot_per_brand(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    with patch.dict(trs.PLATFORMS, {"youtube": _FakeYouTube}):
        findings = service.collect_platform("youtube", ["Firman", "Honda"])
    assert len(findings) == 2
    assert set(repo.latest_findings("YouTube")) == {"Firman", "Honda"}


# ── Service: gap analysis ─────────────────────────────────────────────────────

def _seed_youtube(repo, firman_videos, honda_videos):
    repo.save_findings("YouTube", [
        {"brand": "Firman", "platform": "YouTube", "video_results": firman_videos,
         "recent_videos_365d": 10, "top_videos_total_views": 1000, "error": ""},
        {"brand": "Honda", "platform": "YouTube", "video_results": honda_videos,
         "recent_videos_365d": 10, "top_videos_total_views": 1000, "error": ""},
    ])


def test_gap_analysis_flags_meaningful_lead_with_why_and_tactics(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=100, honda_videos=900)
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")

    gaps = [f for f in findings if f["type"] == "gap"]
    assert gaps, "9x video lead must produce a gap finding"
    video_gap = next(f for f in gaps if "videos (estimated" in f["metric_label"])
    assert video_gap["leader_brand"] == "Honda"
    assert video_gap["ratio"] == 9.0
    assert "AI" in video_gap["why"]
    assert any("50K-500K" in t for t in video_gap["tactics"])


def test_gap_analysis_reports_strength_when_target_leads(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=900, honda_videos=100)
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")
    video = next(f for f in findings if "videos (estimated" in f["metric_label"])
    assert video["type"] == "strength"


def test_gap_analysis_ignores_lead_within_noise_threshold(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=100, honda_videos=120)  # 1.2x < 1.5x bar
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")
    labels = [f["metric_label"] for f in findings if f["type"] == "gap"]
    assert not any("videos (estimated" in l for l in labels)


def test_gap_analysis_resolves_target_brand_case_insensitively(tmp_path):
    """#82's fix applies here too — Settings casing must not zero out the page."""
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=100, honda_videos=900)
    service = TargetedReviewService(FakeConfig(), "FIRMAN", repository=repo)
    findings = service.gap_analysis("youtube")
    assert findings and findings[0]["target_brand"] == "Firman"


def test_gap_analysis_flags_rating_below_floor_even_when_leading(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    repo.save_findings("Retail Listings", [
        {"brand": "Firman", "platform": "Retail Listings", "total_reviews": 500,
         "avg_rating": 3.8, "error": ""},
        {"brand": "Honda", "platform": "Retail Listings", "total_reviews": 400,
         "avg_rating": 3.7, "error": ""},
    ])
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("retail")
    rating = next(f for f in findings if "star rating" in f["metric_label"])
    assert rating["type"] == "gap"  # 3.8 < 4.0 floor, despite leading Honda


def test_platform_ready_reports_missing_credentials():
    service = TargetedReviewService(FakeConfig(), "Firman",
                                    repository=MagicMock())
    ready, reason = service.platform_ready("youtube")
    assert ready is False
    assert "API Key" in reason

    ready_service = TargetedReviewService(
        FakeConfig({("youtube", "api_key"): "k"}), "Firman", repository=MagicMock())
    ready, reason = ready_service.platform_ready("youtube")
    assert ready is True
