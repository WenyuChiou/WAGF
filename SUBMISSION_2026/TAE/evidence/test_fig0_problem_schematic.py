import fig0_problem_schematic as fig0


def test_directional_claim_requires_governed_high_below_ungoverned():
    assert fig0._directional_claim_error(37.08, 82.80) is None

    error = fig0._directional_claim_error(82.80, 37.08)
    assert error is not None
    assert "directional claim reversed" in error


def test_marker_replacement_rejects_unused_or_unfilled_markers():
    tex, marker_count, replacement_count = fig0._replace_tex_markers("plain tex", {})
    assert tex == "plain tex"
    assert marker_count == 0
    assert replacement_count == 0

    try:
        fig0._replace_tex_markers("plain tex", {"__STALE__": "x"})
    except ValueError as exc:
        assert "unused replacement" in str(exc)
    else:
        raise AssertionError("unused replacement marker did not fail")

    try:
        fig0._replace_tex_markers("hello __MISSING__", {})
    except ValueError as exc:
        assert "unfilled marker" in str(exc)
    else:
        raise AssertionError("unfilled template marker did not fail")


def test_layout_checker_fails_when_text_enters_unowned_region():
    text_boxes = {
        "owned": (1.0, 1.0, 8.0, 5.0),
        "other": (21.0, 1.0, 28.0, 5.0),
    }
    regions = {
        "owned_region": (0.0, 0.0, 10.0, 6.0),
        "foreign_region": (20.0, 0.0, 30.0, 6.0),
    }
    allowed = {
        "owned": {"owned_region"},
        "other": {"foreign_region"},
    }

    violations, min_sep = fig0._layout_violations(text_boxes, regions, allowed)
    assert violations == []
    assert min_sep == 13.0

    mutated = dict(text_boxes)
    mutated["owned"] = (21.0, 1.0, 28.0, 5.0)

    violations, min_sep = fig0._layout_violations(mutated, regions, allowed)
    assert any("owned enters foreign_region" in item for item in violations)
    assert min_sep == 0.0


def test_layout_checker_requires_text_to_fit_inside_allowed_region():
    text_boxes = {"label": (1.0, -0.5, 4.0, 2.0)}
    regions = {"allowed_region": (0.0, 0.0, 5.0, 3.0)}
    allowed = {"label": {"allowed_region"}}

    violations, _ = fig0._layout_violations(text_boxes, regions, allowed)

    assert violations == ["label is not contained by an allowed region"]


def test_active_template_is_record_and_measurement_lens_composition():
    assert "agent answer" in fig0.FIGURE_SPEC
    assert "same field" in fig0.FIGURE_SPEC
    assert "selects records" in fig0.FIGURE_SPEC
    assert "reads self-report" in fig0.FIGURE_SPEC
    assert "Increase actions in selected records" in fig0.FIGURE_SPEC
    assert "conditional rate" in fig0.FIGURE_SPEC
    assert "Records reporting high scarcity" in fig0.FIGURE_SPEC
    assert "agent output" not in fig0.FIGURE_SPEC
    assert "conformance rate" not in fig0.FIGURE_SPEC


def test_active_template_does_not_promote_the_measurement_slice_to_runtime_nodes():
    # These labels belonged to the image-generated D4 exploration. They are
    # intentionally absent from the WAGF-faithful release graph because they
    # imply a separate runtime filter or a new simulation record.
    for misleading_label in ("record filter", "new answer", "shared reported state"):
        assert misleading_label not in fig0.FIGURE_SPEC


def test_active_template_keeps_action_and_state_roles_distinct():
    assert "action" in fig0.FIGURE_SPEC
    assert "same field" in fig0.FIGURE_SPEC


def test_shared_fill_probes_cover_the_two_roles_of_the_state_field():
    assert set(fig0.SHARED_FILL_PROBES) == {
        "inside_reported_state",
        "inside_measure_denominator",
    }
