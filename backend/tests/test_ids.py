from persian_ai_pulse.ids import article_id, normalize_url


def test_normalize_url_strips_tracking_params():
    dirty = "https://Example.com/Post/?utm_source=newsletter&id=42&utm_campaign=x"
    clean = "https://example.com/Post?id=42"
    assert normalize_url(dirty) == normalize_url(clean)


def test_normalize_url_strips_trailing_slash_and_fragment():
    a = normalize_url("https://example.com/post/")
    b = normalize_url("https://example.com/post#section-2")
    assert a == b


def test_article_id_is_stable_across_equivalent_urls():
    id_a = article_id("https://example.com/post/?utm_source=x")
    id_b = article_id("https://EXAMPLE.com/post?utm_campaign=y")
    assert id_a == id_b


def test_article_id_differs_for_different_urls():
    assert article_id("https://example.com/a") != article_id("https://example.com/b")


def test_article_id_is_short_and_hex():
    result = article_id("https://example.com/a")
    assert len(result) == 16
    int(result, 16)  # raises ValueError if not hex
