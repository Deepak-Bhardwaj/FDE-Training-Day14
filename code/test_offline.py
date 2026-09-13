"""
test_offline.py
---------------
Runs the whole Lab 9 orchestration OFFLINE (no Azure, no CrewAI LLM calls) and
asserts each behaviour. Run:  python test_offline.py
"""
from pipeline import run_once
from service_bus import LocalBus
from verifier import verify, mape
from cost import ALL_PREMIUM, ROUTED, estimate_run_cost
from chaos import run_drill


def test_happy_path():
    r = run_once(bus=LocalBus(), agent_models=ROUTED)
    assert r["final_status"] == "forecast.approved", r["final_status"]
    assert r["verifier"]["passed"]
    assert r["mape"] < 25, r["mape"]
    assert "forecast.approved" in r["events"]
    print(f"[happy path] approved, MAPE={r['mape']}%, cost/decision=${r['cost_per_decision_usd']}")


def test_routing_saves_money():
    premium = estimate_run_cost(ALL_PREMIUM).total_usd
    routed = estimate_run_cost(ROUTED).total_usd
    assert routed < premium, (routed, premium)
    saving = 100 * (1 - routed / premium)
    print(f"[cost] routed ${routed:.4f} vs premium ${premium:.4f} -> {saving:.0f}% cheaper")
    assert saving > 40


def test_verifier_catches_bad_forecast():
    good = run_once(bus=LocalBus())["forecast"]
    bad = dict(good); bad[next(iter(bad))] = 10_000_000
    assert verify(bad).passed is False
    print("[verifier] caught an over-capacity spike")


def test_chaos_bad_data_is_caught():
    out = run_drill(["bad_sales_data"])
    card = out["scorecard"]
    assert card["stayed_up"] and card["verifier_caught"], card
    print(f"[chaos: bad_sales_data] score {card['score_out_of_4']}/4, verifier caught it")


def test_chaos_timeout_recovers():
    out = run_drill(["sales_timeout"])
    assert out["scorecard"]["stayed_up"], out["scorecard"]
    print(f"[chaos: sales_timeout] stayed up via retry, score {out['scorecard']['score_out_of_4']}/4")


def test_chaos_cost_spike_flagged():
    out = run_drill(["cost_spike"])
    card = out["scorecard"]
    # all-premium blows the per-decision budget, so cost_controlled should be False
    assert card["cost_controlled"] is False, card
    print(f"[chaos: cost_spike] budget breach detected, score {card['score_out_of_4']}/4")


if __name__ == "__main__":
    print("Running Lab 9 offline tests...\n")
    test_happy_path()
    test_routing_saves_money()
    test_verifier_catches_bad_forecast()
    test_chaos_bad_data_is_caught()
    test_chaos_timeout_recovers()
    test_chaos_cost_spike_flagged()
    print("\nALL OFFLINE TESTS PASSED")
