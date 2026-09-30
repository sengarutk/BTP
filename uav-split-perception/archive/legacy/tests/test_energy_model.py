import pytest
from evaluation.energy_model import UAVEnergyModel


@pytest.fixture(scope="module")
def energy_model():
    return UAVEnergyModel()


def test_quadcopter_hover_power(energy_model):
    """Assert quadcopter hover power satisfies momentum theory equation dynamically."""
    p_hover = energy_model.compute_aerodynamic_hover_power(
        mass_kg=1.2,
        gravity_mps2=9.81,
        air_density_kgpm3=1.225,
        rotor_area_m2=0.20,
        figure_of_merit=0.70,
        power_profile_drag_w=15.0,
        motor_esc_efficiency=0.75,
    )
    # T = 1.2 * 9.81 = 11.772 N
    # v_i = sqrt(11.772 / (2 * 1.225 * 0.20)) = 4.901478 m/s
    # P_induced = 11.772 * 4.901478 = 57.7002 W
    # P_hover = (57.7002 + 15.0) / (0.70 * 0.75) = 138.4766 W
    assert round(p_hover, 2) == 138.48, f"Quadcopter hover power {p_hover}W does not equal expected 138.48W"

    # Assert dynamic scaling across varying quadcopter masses
    for m in [0.8, 1.0, 1.5, 2.0]:
        t = m * 9.81
        vi = (t / (2 * 1.225 * 0.20)) ** 0.5
        exp = (t * vi + 15.0) / (0.70 * 0.75)
        calc = energy_model.compute_aerodynamic_hover_power(mass_kg=m)
        assert abs(calc - exp) < 1e-4

    # Strict monotonicity with drone mass
    assert energy_model.compute_aerodynamic_hover_power(mass_kg=2.0) > energy_model.compute_aerodynamic_hover_power(mass_kg=1.5)


def test_baseline_platform_power(energy_model):
    """Assert baseline platform power P_base = Hover (dynamic) + Avionics 15W."""
    hover_p = energy_model.compute_aerodynamic_hover_power()
    p_base = energy_model.profile.p_hover_w + energy_model.profile.p_avionics_w
    assert round(p_base, 2) == round(hover_p + 15.0, 2)


def test_mission_flight_lifetime(energy_model):
    """Assert mission flight lifetime falls within standard quadcopter flight envelope [18, 28] minutes."""
    dc_res = energy_model.compute_duty_cycle_power(
        payload_bytes=800 * 1024,
        bw_mbps=20.0,
        target_fps=30.0,
    )
    e_breakdown = energy_model.compute_energy_breakdown(
        t_edge_ms=1.25,
        t_quant_ms=0.20,
        t_tx_ms=dc_res["t_tx_ms"],
        t_cloud_ms=5.56,
    )
    lifetime_minutes = energy_model.estimate_battery_lifetime_minutes(
        e_edge_mj=e_breakdown["e_edge_mj"],
        e_quant_mj=e_breakdown["e_quant_mj"],
        p_tx_avg_w=dc_res["p_tx_avg_w"],
        delivered_fps=dc_res["delivered_fps"],
    )
    assert 18.0 <= lifetime_minutes <= 28.0, (
        f"Mission flight lifetime {lifetime_minutes:.2f} min falls outside [18.0, 28.0] minutes"
    )
