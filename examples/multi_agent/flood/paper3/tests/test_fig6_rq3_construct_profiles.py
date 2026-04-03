from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[5]
SCRIPT_PATH = (
    ROOT
    / "examples"
    / "multi_agent"
    / "flood"
    / "paper3"
    / "figures"
    / "scripts"
    / "fig6_rq3_construct_profiles.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("fig6_rq3_construct_profiles", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_prepare_scatter_profiles_and_render_outputs():
    module = load_module()

    profiles = module.compute_scatter_profiles(module.YEARLY_PATH)

    assert set(profiles) == {"MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"}
    assert profiles["MG-Owner"]["SP"] == 2.546562
    assert profiles["MG-Owner"]["PA"] == 3.007969
    assert profiles["NMG-Owner"]["SP"] == 2.686169
    assert profiles["NMG-Renter"]["PA"] == 2.646462

    fig = module.build_figure()
    assert len(fig.axes) == 3

    output_dir = ROOT / "examples" / "multi_agent" / "flood" / "paper3" / "figures" / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "fig6.png"
    pdf_path = output_dir / "fig6.pdf"
    module.save_outputs(fig, png_path, pdf_path)

    assert png_path.exists()
    assert pdf_path.exists()
