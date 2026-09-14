from engine import ShopifyCatalogEngine


def test_engine_initialization():
    engine = ShopifyCatalogEngine("https://example.com/")
    assert engine.base_url == "https://example.com"
    assert "User-Agent" in engine.headers


def test_invalid_domain_handles_gracefully():
    engine = ShopifyCatalogEngine("https://invalid-domain-target-never-exists-xyz.com")
    products = engine.fetch_page(page=1)
    assert products == []