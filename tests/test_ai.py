from valheim_vn.ai import ECONOMY_MODEL, _run_route
from valheim_vn.schema import Tier


def test_economy_route_is_one_phrase_and_luna_only() -> None:
    route = _run_route(Tier.ULTRA, economy=True)

    assert route.model == ECONOMY_MODEL == "gpt-5.6-luna"
    assert route.review_model == ECONOMY_MODEL
    assert route.batch_size == 1
    assert route.effort == "none"
    assert route.review_effort == "none"


def test_quality_route_is_unchanged() -> None:
    route = _run_route(Tier.ULTRA, economy=False)

    assert route.model == "gpt-5.6-sol"
    assert route.review_model == "gpt-5.6-sol"
    assert route.batch_size == 2
