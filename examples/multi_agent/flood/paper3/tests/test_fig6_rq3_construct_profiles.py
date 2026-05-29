from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[5]
# The fig6 figure script is the ``_v2`` redesign that actually ships in
# figures/scripts/ (the original non-``_v2`` name this test pointed at was
# never committed — git log --all is empty for it). The _v2 module exposes
# ``compute_group_profiles()`` (a no-arg DataFrame builder) rather than the
# never-committed ``compute_scatter_profiles(path)`` dict API, but produces
# the identical per-group SP/PA means and the same 3-axis figure, so the
# expected values below are unchanged — only the entrypoint names differ.
SCRIPT_PATH = (
    ROOT
    / "examples"
    / "multi_agent"
    / "flood"
    / "paper3"
    / "figures"
    / "scripts"
    / "fig6_rq3_construct_profiles_v2.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "fig6_rq3_construct_profiles_v2", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_group_profiles_and_render_outputs():
    module = load_module()

    profiles = module.compute_group_profiles().set_index("group")

    assert set(profiles.index) == {"MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"}
    assert round(float(profiles.loc["MG-Owner", "SP"]), 6) == 2.546562
    assert round(float(profiles.loc["MG-Owner", "PA"]), 6) == 3.007969
    assert round(float(profiles.loc["NMG-Owner", "SP"]), 6) == 2.686169
    assert round(float(profiles.loc["NMG-Renter", "PA"]), 6) == 2.646462

    fig = module.build_figure()
    assert len(fig.axes) == 3

    output_dir = ROOT / "examples" / "multi_agent" / "flood" / "paper3" / "figures" / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "fig6.png"
    pdf_path = output_dir / "fig6.pdf"
    fig.savefig(png_path)
    fig.savefig(pdf_path)

    assert png_path.exists()
    assert pdf_path.exists()
