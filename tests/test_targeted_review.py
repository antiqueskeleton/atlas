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
from backend.targeted_review.targeted_review_service import (
    TargetedReviewService, build_presence_block,
)
from backend.targeted_review.youtube_provider import (
    YouTubePlatformProvider, _filter_relevant,
)


class FakeConfig:
    def __init__(self, creds: dict | None = None):
        self._creds = creds or {}

    def get_platform_credential(self, platform, field):
        return self._creds.get((platform, field), "")


# ── YouTube provider ──────────────────────────────────────────────────────────

def _yt_item(video_id, title):
    return {"video_id": video_id, "title": title, "channel": "c",
            "published": "2026-01-15", "views": 0}


def test_youtube_no_key_returns_in_band_error():
    provider = YouTubePlatformProvider()
    result = provider.fetch_brand_presence("Firman")
    assert "No YouTube API key" in result["error"]
    assert result["brand"] == "Firman"


def test_youtube_relevance_filter_drops_off_topic_and_off_brand_titles():
    """
    Pinned against REAL contamination observed with live credentials
    (2026-07-06): searching '"CAT" generator' returned literal cat-the-
    animal videos ("Flying Horse - Gatorrada (Cat-Toast)") with millions of
    views. A title only counts when it mentions the brand (word-boundary,
    so 'category' doesn't match 'CAT') AND a generator-market term.
    """
    items = [
        _yt_item("a", "Cat RP12000E Generator Review | 12,000 Watt Portable"),
        _yt_item("b", "Flying Horse - Gatorrada (Cat-Toast)"),      # no market term
        _yt_item("c", "Best AI video generator tools 2026"),        # no brand word
        _yt_item("d", "Shopping by category: generator deals"),     # 'category' != CAT
        _yt_item("e", "TOP 5: Best Caterpillar Portable Generators"),  # no 'CAT' token
    ]
    kept = _filter_relevant(items, "CAT")
    kept_ids = {v["video_id"] for v in kept}
    assert "a" in kept_ids            # real Cat generator review survives
    assert kept_ids == {"a"}          # every junk pattern above is dropped


def test_youtube_relevance_filter_deduplicates_video_ids():
    items = [_yt_item("a", "Firman W03083 generator review")] * 3
    assert len(_filter_relevant(items, "Firman")) == 1


def test_youtube_relevance_filter_allows_plural_brand():
    """Pinned to real data (2026-07-07): titles/comments using the plural
    ("Firmans") must match, same as the core pipeline's word-boundary rule
    (#87) — a bespoke regex here previously lacked that plural allowance."""
    items = [_yt_item("a", "The Firmans are great generators for camping")]
    assert len(_filter_relevant(items, "Firman")) == 1


def test_youtube_counted_metrics_and_error_path():
    provider = YouTubePlatformProvider()
    provider.set_credentials({"api_key": "k"})

    search_page = {
        "items": [
            {"id": {"videoId": "abc"}, "snippet": {"title": "Firman W03083 generator review",
             "channelTitle": "Generatorist", "publishedAt": "2026-01-15T00:00:00Z"}},
            {"id": {"videoId": "junk"}, "snippet": {"title": "Firman family vlog",
             "channelTitle": "Vlogs", "publishedAt": "2026-01-16T00:00:00Z"}},
        ],
    }
    stats_page = {"items": [{"id": "abc", "statistics": {"viewCount": "150000"}}]}

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock(status_code=200)
        resp.json.return_value = stats_page if "videos" in url else search_page
        return resp

    with patch("backend.targeted_review.youtube_provider.requests.get", side_effect=fake_get):
        result = provider.fetch_brand_presence("Firman")

    assert result["error"] == ""
    assert result["relevant_results_top100"] == 1   # vlog filtered out
    assert result["top_videos"][0]["views"] == 150000
    assert result["top_videos_total_views"] == 150000

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
                "relevant_results_top100": {"Firman": 10, "Honda": 90}.get(brand, 0),
                "recent_relevant_365d": 5, "top_videos": [],
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
        {"brand": "Firman", "platform": "YouTube",
         "relevant_results_top100": firman_videos,
         "recent_relevant_365d": 10, "top_videos_total_views": 1000, "error": ""},
        {"brand": "Honda", "platform": "YouTube",
         "relevant_results_top100": honda_videos,
         "recent_relevant_365d": 10, "top_videos_total_views": 1000, "error": ""},
    ])


def test_gap_analysis_flags_meaningful_lead_with_why_and_tactics(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=10, honda_videos=90)
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")

    gaps = [f for f in findings if f["type"] == "gap"]
    assert gaps, "9x relevant-video lead must produce a gap finding"
    video_gap = next(f for f in gaps if "top-100 search results" in f["metric_label"])
    assert video_gap["leader_brand"] == "Honda"
    assert video_gap["ratio"] == 9.0
    assert "AI" in video_gap["why"]
    assert any("50K-500K" in t for t in video_gap["tactics"])


def test_gap_analysis_reports_strength_when_target_leads(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=90, honda_videos=10)
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")
    video = next(f for f in findings if "top-100 search results" in f["metric_label"])
    assert video["type"] == "strength"


def test_gap_analysis_ignores_lead_within_noise_threshold(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=50, honda_videos=60)  # 1.2x < 1.5x bar
    service = TargetedReviewService(FakeConfig(), "Firman", repository=repo)
    findings = service.gap_analysis("youtube")
    labels = [f["metric_label"] for f in findings if f["type"] == "gap"]
    assert not any("top-100 search results" in l for l in labels)


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


# ── Intelligence Engine presence block ────────────────────────────────────────

def test_build_presence_block_summarizes_platforms_with_measured_gaps(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    _seed_youtube(repo, firman_videos=100, honda_videos=900)
    repo.save_findings("Editorial Coverage", [
        {"brand": "Firman", "platform": "Editorial Coverage",
         "sites_with_coverage": 2, "sites_checked": 6, "total_results": 40,
         "strongest_site": "Bob Vila", "error": ""},
    ], collected_at="2026-07-06T12:00:00")

    block = build_presence_block(repo, "Firman")

    assert "YouTube (collected" in block
    assert "Firman: 100 relevant videos in the top-100 search results" in block
    assert "Honda: 900 relevant videos in the top-100 search results" in block
    # Pre-validated deterministic comparison, so the LLM never re-derives it
    assert "MEASURED GAP" in block
    assert "Editorial Coverage (collected 2026-07-06)" in block
    assert "covered by 2 of 6 tracked authority review sites" in block
    assert "strongest: Bob Vila" in block


def test_build_presence_block_reports_explicit_empty_state(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    block = build_presence_block(repo, "Firman")
    assert "No measured platform data collected yet" in block
    assert "Do not invent platform numbers" in block


def test_build_presence_block_skips_error_only_platforms(tmp_path):
    """A platform where every brand failed (e.g. bad key) must not appear
    as a section of zeros — absence, not fake measurements."""
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    repo.save_findings("Reddit", [
        {"brand": "Firman", "platform": "Reddit", "error": "Reddit auth failed"},
    ])
    block = build_presence_block(repo, "Firman")
    assert "Reddit" not in block
    assert "No measured platform data collected yet" in block


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


# ── Social discovery + channel metrics (user request 2026-07-06) ────────────

_SITE_HTML = """
<html><body><footer>
<a href="https://www.youtube.com/@FirmanPowerEquipment">YouTube</a>
<a href="https://www.facebook.com/FirmanPower">Facebook</a>
<a href="https://www.instagram.com/firmanpower/">Instagram</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
<a href="/products">Products</a>
</footer></body></html>
"""


def test_extract_social_links_finds_profiles_and_skips_share_links():
    from backend.targeted_review.social_discovery import extract_social_links
    links = extract_social_links(_SITE_HTML)
    assert links["youtube"] == "https://www.youtube.com/@FirmanPowerEquipment"
    assert links["facebook"] == "https://www.facebook.com/FirmanPower"
    assert "instagram" in links
    assert "sharer" not in links.get("facebook", "")


def test_social_links_repository_roundtrip(tmp_path):
    repo = TargetedReviewRepository(db_path=tmp_path / "t.db")
    repo.save_social_links("Firman", {"youtube": "https://youtube.com/@x"})
    repo.save_social_links("Firman", {"youtube": "https://youtube.com/@y"})  # update wins
    assert repo.get_social_links("Firman")["youtube"] == "https://youtube.com/@y"
    assert repo.get_social_links("Unknown") == {}
    assert "Firman" in repo.all_social_links()


def test_channel_lookup_params_forms():
    from backend.targeted_review.youtube_provider import _channel_lookup_params
    assert _channel_lookup_params("https://www.youtube.com/channel/UCabc-1") == {"id": "UCabc-1"}
    assert _channel_lookup_params("https://youtube.com/@Firman") == {"forHandle": "Firman"}
    assert _channel_lookup_params("https://www.youtube.com/user/gen") == {"forUsername": "gen"}
    assert _channel_lookup_params("https://www.youtube.com/c/Custom") is None
    assert _channel_lookup_params("") is None


def test_channel_metrics_parsed_from_api_payloads():
    from backend.targeted_review.youtube_provider import YouTubePlatformProvider
    provider = YouTubePlatformProvider()

    channels_payload = {"items": [{
        "statistics": {"subscriberCount": "15200", "viewCount": "9000000",
                       "videoCount": "240"},
        "contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}},
    }]}
    playlist_payload = {"items": [
        {"contentDetails": {"videoPublishedAt": "2026-06-01T00:00:00Z"}},
        {"contentDetails": {"videoPublishedAt": "2020-01-01T00:00:00Z"}},
    ]}

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock(status_code=200)
        resp.json.return_value = (playlist_payload if "playlistItems" in url
                                  else channels_payload)
        return resp

    with patch("backend.targeted_review.youtube_provider.requests.get",
               side_effect=fake_get):
        result = provider._channel_metrics("key", "https://youtube.com/@Firman")

    assert result["channel_subscribers"] == 15200
    assert result["channel_video_count"] == 240
    assert result["channel_uploads_365d"] == 1   # only the 2026 upload counts
    assert result["channel_latest_upload"] == "2026-06-01"


def test_channel_metrics_degrade_to_empty_without_url():
    from backend.targeted_review.youtube_provider import YouTubePlatformProvider
    result = YouTubePlatformProvider()._channel_metrics("key", "")
    assert result["channel_subscribers"] is None
    assert result["channel_url"] == ""


# ── Owner-voice comment mining (user request 2026-07-06) ─────────────────────

def test_analyze_comments_tags_signals_and_counts():
    from backend.targeted_review.youtube_provider import _analyze_comments
    comments = [
        {"text": "I would definitely recommend the Firman tri-fuel.", "likes": 5},
        {"text": "My Firman would not start after two months, avoid it.", "likes": 9},
        {"text": "Firman runs my whole panel.", "likes": 2},
        {"text": "Great video, thanks for sharing!", "likes": 1},
        {"text": "Firmania is a made-up word.", "likes": 0},  # word boundary
        {"text": "The firmans are good generators, very reliable.", "likes": 3},
    ]
    voice = _analyze_comments(comments, "Firman")
    assert voice["comments_sampled"] == 6
    assert voice["mentioning_brand"] == 4        # boundary excludes 'Firmania'
    assert comments[5]["signal"] == "mention"    # plural 'firmans' still counts
    assert voice["recommendation_cues"] >= 1
    assert voice["negative_cues"] >= 1
    signals = [c["signal"] for c in comments]
    assert "recommend" in signals and "negative" in signals
    assert comments[3]["signal"] == ""           # non-mention untouched


def test_top_video_comments_skips_disabled_and_caps(tmp_path):
    from backend.targeted_review.youtube_provider import YouTubePlatformProvider
    provider = YouTubePlatformProvider()

    ok_payload = {"items": [
        {"snippet": {"topLevelComment": {"snippet": {
            "textDisplay": f"comment {i}", "likeCount": i}}}}
        for i in range(15)
    ]}

    calls = []
    def fake_get(url, params=None, timeout=None):
        calls.append(params["videoId"])
        resp = MagicMock()
        if params["videoId"] == "disabled":
            resp.status_code = 403   # commentsDisabled
        else:
            resp.status_code = 200
            resp.json.return_value = ok_payload
        return resp

    videos = [{"video_id": "a", "title": "T1"}, {"video_id": "disabled", "title": "T2"},
              {"video_id": "b", "title": "T3"}]
    with patch("backend.targeted_review.youtube_provider.requests.get",
               side_effect=fake_get):
        comments = provider._top_video_comments("key", videos)

    assert len(calls) == 3
    assert len(comments) == 30            # 15 + 0 (disabled skipped) + 15
    assert all(c["video"] in ("T1", "T3") for c in comments)


# ── Best Buy provider (#98) ───────────────────────────────────────────────────

def test_bestbuy_parse_filters_by_brand_and_aggregates():
    from backend.targeted_review.bestbuy_provider import parse_bestbuy_products
    products = [
        {"name": "FIRMAN 4550W Generator", "customerReviewCount": 100,
         "customerReviewAverage": "4.5", "salePrice": 499.0},
        {"name": "FIRMAN Tri-Fuel 8000W", "customerReviewCount": 300,
         "customerReviewAverage": "4.0", "salePrice": 999.0},
        {"name": "Generator cover for Honda", "customerReviewCount": 999,
         "customerReviewAverage": "5.0", "salePrice": 20.0},  # not a Firman name
    ]
    parsed = parse_bestbuy_products(products, "Firman")
    assert parsed["listings_found"] == 2
    assert parsed["total_reviews"] == 400
    assert parsed["avg_rating"] == 4.12   # (4.5*100 + 4.0*300) / 400
    assert parsed["top_products"][0]["reviews"] == 300


def test_bestbuy_no_key_returns_in_band_error():
    from backend.targeted_review.bestbuy_provider import BestBuyProvider
    result = BestBuyProvider().fetch_brand_presence("Firman")
    assert "No Best Buy API key" in result["error"]


# ── AI Overviews provider (#97) ───────────────────────────────────────────────

def test_ai_overview_text_extraction_flattens_nested_blocks():
    from backend.targeted_review.ai_overview_provider import extract_overview_text
    block = {"text_blocks": [
        {"type": "paragraph", "snippet": "Top picks include Honda and Generac."},
        {"type": "list", "list": [{"title": "Honda EU2200i", "snippet": "quiet"}]},
    ]}
    text = extract_overview_text(block)
    assert "Honda and Generac" in text and "EU2200i" in text
    assert extract_overview_text({}) == ""
    assert extract_overview_text({"weird": [1, None]}) == ""


def test_ai_overview_fetch_all_shares_queries_and_flags_brands():
    from backend.targeted_review.ai_overview_provider import (
        AIOverviewProvider, AI_OVERVIEW_QUERIES)
    provider = AIOverviewProvider()
    provider.set_credentials({"api_key": "k"})

    calls = []
    def fake_get(url, params=None, timeout=None):
        calls.append(params["q"])
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"ai_overview": {"text_blocks": [
            {"snippet": "Experts recommend Honda generators for reliability."}]}}
        return resp

    with patch("backend.targeted_review.ai_overview_provider.requests.get",
               side_effect=fake_get):
        findings = provider.fetch_all(["Honda", "Firman"])

    assert len(calls) == len(AI_OVERVIEW_QUERIES)   # shared, not per-brand
    by_brand = {f["brand"]: f for f in findings}
    assert by_brand["Honda"]["appearances"] == 5
    assert by_brand["Firman"]["appearances"] == 0
    assert by_brand["Firman"]["overviews_present"] == 5
    assert by_brand["Firman"]["error"] == ""


def test_ai_overview_no_key_fails_all_brands_in_band():
    from backend.targeted_review.ai_overview_provider import AIOverviewProvider
    findings = AIOverviewProvider().fetch_all(["Firman", "Honda"])
    assert len(findings) == 2
    assert all("No SerpApi key" in f["error"] for f in findings)
