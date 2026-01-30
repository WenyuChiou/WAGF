# Task-061-C7: docs/ Path Fixes & Module Documentation Verification

> **Branch**: `feat/memory-embedding-retrieval`
> **Priority**: MEDIUM
> **Depends on**: Task-061 root README changes (already completed)

## Objective

Verify all documentation links resolve correctly and ensure module documentation is consistent.

## Changes Required

### 1. Verify Broken Path Fixes (Already Fixed in Root README)

The root README.md was rewritten by Task-061. Verify these paths are correct:

| Old Path (was broken) | New Path (should be correct) |
|---|---|
| `docs/skill_architecture.md` | `docs/architecture/skill_architecture.md` |
| `docs/customization_guide.md` | `docs/guides/customization_guide.md` |
| `docs/experiment_design_guide.md` | `docs/guides/experiment_design_guide.md` |
| `docs/agent_assembly.md` | `docs/guides/agent_assembly.md` |

### 2. Verify Module Documentation Pairs

Check that all 7 EN/ZH pairs in `docs/modules/` have aligned content:

| English | Chinese | Check |
|---|---|---|
| `00_theoretical_basis_overview.md` | `00_theoretical_basis_overview_zh.md` | Section alignment |
| `memory_components.md` | `memory_components_zh.md` | Section alignment |
| `reflection_engine.md` | `reflection_engine_zh.md` | Section alignment |
| `governance_core.md` | `governance_core_zh.md` | Section alignment |
| `context_system.md` | `context_system_zh.md` | Section alignment |
| `simulation_engine.md` | `simulation_engine_zh.md` | Section alignment |
| `skill_registry.md` | `skill_registry_zh.md` | Section alignment |

For each pair: verify they have the same number of sections, same table structures, and consistent version references.

### 3. Update Version References

Search all docs/ files for version references and standardize to v3.3:
- Any reference to "v3.0" should be "v3.3"
- Any reference to "v3.1" or "v3.2" should clarify which version they describe (historical is fine, but current should be v3.3)

### 4. Verify Architecture Documentation

- `docs/architecture/architecture.md`: Verify it accurately describes current code structure
- `docs/architecture/mas-five-layers.md`: 760 lines, comprehensive — verify accuracy only, no changes needed
- `docs/architecture/skill_architecture.md`: Verify links from root README work

### 5. Verify Guide Documentation

- `docs/guides/agent_assembly.md`: Verify file exists and is linked correctly from both EN/ZH READMEs
- `docs/guides/agent_assembly_zh.md`: Verify exists (linked from Chinese README)
- `docs/guides/experiment_design_guide.md`: Verify current
- `docs/guides/customization_guide.md`: Verify current

## Reference Files

- `README.md`: Already updated root README (source of truth for links)
- `README_zh.md`: Chinese README (source of truth for ZH links)

## Verification

1. All links in root README.md resolve to existing files
2. All links in root README_zh.md resolve to existing files
3. All module doc pairs have matching section structure
4. Version references are consistent (v3.3 for current)
5. No broken links in any docs/ file
