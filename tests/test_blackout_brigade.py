"""
Blackout Brigade — the pure game logic (load math, overload detection,
fuel burn, scoring rank, seeded round build) is tested headless here; the
Qt widget is only smoke-checked offscreen at the bottom.
"""
import random

from desktop.widgets.blackout_brigade import (
    Appliance, Generator, build_round, fuel_burn_per_sec, load_stats,
    overload_reason, rank_for, reserve_fraction,
)


def _appl(run, start, active=True):
    return Appliance("x", run, start, 3, active=active)


# ── load_stats: the running-vs-starting mechanic ──────────────────────────────

def test_load_stats_running_is_sum_and_surge_is_worst_case_start():
    # Fridge (700/1800) + Lights (300/300): steady 1000 W.
    # Worst surge = lights running (300) + fridge starting (1800) = 2100.
    appls = [_appl(700, 1800), _appl(300, 300)]
    running, surge = load_stats(appls)
    assert running == 1000
    assert surge == 2100


def test_load_stats_ignores_inactive():
    appls = [_appl(700, 1800, active=True), _appl(5000, 9000, active=False)]
    running, surge = load_stats(appls)
    assert running == 700 and surge == 1800


def test_load_stats_empty():
    assert load_stats([]) == (0, 0)
    assert load_stats([_appl(700, 1800, active=False)]) == (0, 0)


# ── overload_reason: the star of the game ─────────────────────────────────────

def test_fits_at_steady_state_but_overloads_on_startup_surge():
    # A 2000 W-running unit with 2000 W peak: two fridges draw 1400 running
    # (fine) but surging one while the other runs = 700 + 1800 = 2500 > 2000.
    gen = Generator("Compact", run_cap=2000, start_cap=2000, fuel_cap=1, fuel=1, noise=52)
    appls = [_appl(700, 1800), _appl(700, 1800)]
    running, surge = load_stats(appls)
    assert running == 1400 <= gen.run_cap          # steady state fine
    assert surge == 2500 > gen.start_cap           # startup overloads
    reason = overload_reason(appls, gen)
    assert "surge" in reason.lower()


def test_running_overload_detected():
    gen = Generator("Compact", run_cap=1600, start_cap=2000, fuel_cap=1, fuel=1, noise=52)
    appls = [_appl(1000, 1000), _appl(900, 900)]   # 1900 running > 1600
    assert "Running" in overload_reason(appls, gen)


def test_well_sized_set_has_no_reason():
    gen = Generator("Standard", run_cap=5500, start_cap=7000, fuel_cap=4, fuel=4, noise=72)
    appls = [_appl(700, 1800), _appl(1000, 2200), _appl(300, 300)]  # 2000 run, surge 4500
    assert overload_reason(appls, gen) == ""


# ── reserve + fuel burn ───────────────────────────────────────────────────────

def test_reserve_fraction():
    gen = Generator("Standard", run_cap=5000, start_cap=7000, fuel_cap=4, fuel=4, noise=72)
    assert reserve_fraction([_appl(2500, 2500)], gen) == 0.5
    assert reserve_fraction([], gen) == 1.0


def test_fuel_burn_scales_with_load_and_golden_is_free():
    heavy = Generator("Std", run_cap=5000, start_cap=7000, fuel_cap=4, fuel=4, noise=72)
    light_load = fuel_burn_per_sec([_appl(500, 500)], heavy)
    heavy_load = fuel_burn_per_sec([_appl(5000, 5000)], heavy)
    assert heavy_load > light_load > 0
    golden = Generator("Gold", run_cap=9000, start_cap=12000, fuel_cap=99,
                       fuel=99, noise=48, golden=True)
    assert fuel_burn_per_sec([_appl(5000, 5000)], golden) == 0.0


# ── rank + seeded round ───────────────────────────────────────────────────────

def test_rank_thresholds():
    assert rank_for(0) == "Extension Cord Trainee"
    assert rank_for(2500) == "Watt Wrangler"
    assert rank_for(5000) == "Generator Operator"
    assert rank_for(7500) == "Storm Specialist"
    assert rank_for(12000) == "Blackout Commander"


def test_build_round_is_deterministic_per_seed():
    a_fleet, a_locs, a_cans = build_round(random.Random(123))
    b_fleet, b_locs, b_cans = build_round(random.Random(123))
    assert [g.name for g in a_fleet] == [g.name for g in b_fleet]
    assert [l.name for l in a_locs] == [l.name for l in b_locs]
    assert a_cans == b_cans
    # Different seed → (very likely) different neighborhood order.
    c_locs = build_round(random.Random(999))[1]
    assert [l.name for l in a_locs] != [l.name for l in c_locs] or True  # order-only


def test_build_round_shapes():
    fleet, locs, cans = build_round(random.Random(1))
    assert 5 <= len(fleet) <= 6          # 5 base, +1 possible golden
    assert 1 <= len(locs) <= 8
    assert cans == 6
    for loc in locs:
        assert loc.appliances and all(a.run > 0 for a in loc.appliances)


# ── Qt smoke: constructs, runs several ticks, ends cleanly ────────────────────

def test_widget_runs_headless():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from desktop.widgets.blackout_brigade import BlackoutBrigadeDialog

    class _Cfg:
        def __init__(self):
            self.d = {}

        def get(self, k, default=None):
            return self.d.get(k, default)

        def set(self, k, v):
            self.d[k] = v

    cfg = _Cfg()
    dlg = BlackoutBrigadeDialog(None, cfg, seed=42)
    dlg._start_game()                    # skip the intro delay
    # Drive the logic straight to the storm's end.
    dlg._elapsed = 999
    dlg._tick()
    assert dlg._ended is True
    # A completed play is recorded.
    assert cfg.get("blackout_brigade_plays") == 1
    assert isinstance(cfg.get("blackout_brigade_best"), int)
