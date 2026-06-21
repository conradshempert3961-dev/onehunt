from __future__ import annotations

from utils.products import PRODUCT_BY_ID, PRODUCT_CATALOG, PRODUCT_HUNT_TROPHY, PRODUCT_ONEHUNT


def test_product_catalog_has_two_lines() -> None:
    assert len(PRODUCT_CATALOG) == 2
    ids = {item["id"] for item in PRODUCT_CATALOG}
    assert ids == {"onehunt", "hunt_trophy"}


def test_onehunt_pricing_is_lifetime_990() -> None:
    assert PRODUCT_ONEHUNT["price_rub"] == 990
    assert PRODUCT_ONEHUNT["billing"] == "lifetime"


def test_hunt_trophy_pricing_is_monthly_490() -> None:
    assert PRODUCT_HUNT_TROPHY["price_rub"] == 490
    assert PRODUCT_HUNT_TROPHY["billing"] == "monthly"


def test_product_by_id_lookup() -> None:
    assert PRODUCT_BY_ID["onehunt"]["brand"] == "ONEHUNT"
    assert PRODUCT_BY_ID["hunt_trophy"]["brand"] == "Hunt Trophy"
