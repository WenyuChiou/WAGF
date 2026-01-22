# Changelog

All notable changes to the governed_broker_framework project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v0.29.0] - 2026-01-21 - Task-029 MA Pollution Remediation

### BREAKING CHANGES

- **SurveyRecord No Longer Has Flood Fields**
  - `flood_experience`, `financial_loss` fields removed from base `SurveyRecord`
  - Use `FloodSurveyLoader` from `examples/multi_agent/survey/` for MA-specific fields

- **AgentProfile Uses Extensions Dict**
  - `flood_zone`, `base_depth_m`, `flood_probability` no longer direct attributes
  - Access via `profile.extensions["flood"].field_name`

- **AgentInitializer No Longer Has mg_classifier Parameter**
  - Use `MAAgentInitializer` from `examples/multi_agent/survey/` for MG classification

- **Enrichment API Changed**
  - `include_hazard=True` → `position_enricher=DepthSampler()`
  - `include_rcv=True` → `value_enricher=RCVGenerator()`
  - Old parameters removed (were deprecated in v0.28)

### Added

- **Protocol-Based Dependency Injection** (`broker/interfaces/enrichment.py`)
  - `PositionEnricher` protocol for spatial data assignment
  - `ValueEnricher` protocol for asset value calculation
  - `PositionData` and `ValueData` named tuples

- **MA-Specific Survey Module** (`examples/multi_agent/survey/`)
  - `FloodSurveyLoader` - Survey loader with flood experience fields
  - `FloodSurveyRecord` - Record with flood-specific attributes
  - `MGClassifier` - Marginalized Group classification (moved from broker/)
  - `MAAgentInitializer` - MA-specific agent initialization with MG integration
  - `MAAgentProfile` - Extended profile with flood extension flattening

- **Architecture Documentation** (`ARCHITECTURE.md`)
  - Protocol-based dependency injection patterns
  - Extensions pattern for domain-specific data
  - Config-driven domain logic documentation

- **Migration Guide** (`.tasks/handoff/task-029-migration-guide.md`)
  - Breaking changes with before/after code examples
  - Quick migration checklist

### Changed

- **AgentProfile Classification Fields** (Generic naming)
  - `is_mg` → `is_classified` (with backward-compat alias)
  - `mg_score` → `classification_score` (with backward-compat alias)
  - `mg_criteria` → `classification_criteria` (with backward-compat alias)
  - `group_label` now returns "A"/"B" instead of "MG"/"NMG"

- **AgentInitializer Methods** (Generic naming)
  - `enrich_with_hazard()` → `enrich_with_position()`
  - `enrich_with_rcv()` → `enrich_with_values()`
  - `_create_extensions()` now returns empty dict (override in subclass)

- **Memory Tags** (Config-driven)
  - Tags now loaded from `agent_types.yaml` `memory_config.retrieval_tags`
  - No hardcoded "MG" → "subsidy" mapping in broker/

- **Media Context Fields** (Generic naming)
  - `social_media` → `peer_messages`
  - `news` → `broadcast`

### Removed

- **Hardcoded MA Examples** from broker/ docstrings
  - reflection_engine.py - Removed flood damage examples
  - memory.py - Changed "household_mg" to generic examples
  - context_builder.py - Removed flood-specific field names

- **Path Traversal Anti-Pattern**
  - Removed `sys.path.insert()` hack in agent_initializer.py
  - Domain code no longer imported via path manipulation

### Deprecated

- **Backward Compatibility Aliases** (will be removed in v0.31)
  - `AgentProfile.is_mg` → use `is_classified`
  - `AgentProfile.mg_score` → use `classification_score`
  - `AgentProfile.mg_criteria` → use `classification_criteria`

### Documentation

- **Audit Report** (`.tasks/handoff/task-029-audit-report.md`)
  - Grep audit confirming zero executable MA code in broker/
  - Status: PASS

---

## [2026-01-21] - Task-028 Import Path Fixes

### Fixed
- **Import Errors After File Relocation** (Critical)
  - Fixed 6 import path errors across 4 files after Codex moved files from `broker/` to `examples/multi_agent/`
  - Files affected:
    - `examples/multi_agent/environment/catastrophe.py` - Changed to relative import (`.hazard`)
    - `examples/multi_agent/environment/hazard.py` - Fixed 3 imports (`.prb_loader`, `.depth_sampler`, `.vulnerability`)
    - `examples/multi_agent/hazard/prb_analysis.py` - Updated to new path
    - `examples/multi_agent/tests/test_module_integration.py` - Updated test import
  - Root cause: File moves completed but internal imports not updated
  - Verification: All modules now import successfully ✅

### Changed
- **Task-028 Status Update**
  - 028-C (Move media_channels.py): Marked as completed
  - 028-D (Move hazard module): Marked as completed
  - 028-G (Run verification tests): Status changed from `blocked` to `ready_for_execution`
  - Import fixes documented in artifacts-index.json (028-C-FIX, 028-D-FIX, 028-D-FIX2, 028-D-FIX3)

---

## [2026-01-21] - Workflow Improvement Implementation

### Added
- **Status Synchronization Tool** (`.tasks/scripts/validate_sync.py`)
  - 274 lines, validates registry.json ↔ handoff file status consistency
  - Supports `--fix` flag for auto-correction
  - Successfully detected and helped fix Task-015 status mismatch

- **Dependency Checker** (`.tasks/scripts/check_unblock.py`)
  - 301 lines, checks blocked tasks and auto-unblocks when dependencies complete
  - New blocker format: dict with `depends_on`, `unblock_trigger`, `unblock_action`
  - Successfully unblocked Task-028-G after 028-C/D completion

- **Handoff Templates**
  - Simple template (`.tasks/templates/handoff-simple.md`) - for <5 subtasks
  - Complex template (`.tasks/templates/handoff-complex.md`) - for multi-agent tasks

- **Centralized Artifact Registry** (`.tasks/artifacts-index.json`)
  - Tracks all produced files with metadata (task_id, type, producer, timestamp)
  - Currently tracking 21 artifacts

### Changed
- **GUIDE.md Updates**
  - Section 3.1: Status Synchronization protocol
  - Section 6.2: Handoff Templates selection guide
  - Section 7.1: Centralized Artifact Registry
  - Section 10.1: Blocked Task Management (new blocker format)
  - Section 14: Enhanced RELAY Protocol

- **Registry Cleanup**
  - Removed Task-023 (deprecated duplicate of Task-021)
  - Total tasks reduced from 19 to 18
  - All statuses now synchronized between registry.json and handoff files

---

## [2026-01-20] - Task-027 v3 MA Integration

### Added
- **UniversalCognitiveEngine v3 Integration**
  - Integrated Surprise Engine into Multi-Agent system
  - Added CLI parameters: `--arousal-threshold`, `--ema-alpha`, `--stimulus-key`
  - Updated `run_unified_experiment.py` to support `--memory-engine universal`

### Changed
- **YAML Configuration**
  - Added global_config.memory: arousal_threshold, ema_alpha, stimulus_key, ranking_mode
  - Default values: arousal_threshold=2.0, ema_alpha=0.3, stimulus_key="flood_depth_m"

---

## [2026-01-19] - Task-022 PRB Integration & Spatial Features

### Added
- **PRB Flood Data Integration**
  - Copied 13 PRB grid files (2011-2023) to `examples/multi_agent/input/PRB/`
  - Implemented per-agent flood depth calculation based on grid position
  - Added YearMapping class for simulation year ↔ PRB year conversion

- **Spatial Neighborhood Graph**
  - New `SpatialNeighborhoodGraph` class in `broker/components/social_graph.py`
  - Uses actual (grid_x, grid_y) coordinates instead of K-Nearest ring topology
  - Added CLI parameter: `--neighbor-mode spatial`, `--neighbor-radius`

- **Media Channels System**
  - New file: `broker/components/media_channels.py`
  - NewsMediaChannel: delayed, reliable, community-wide
  - SocialMediaChannel: instant, exaggerated (+/-30%), extended network
  - MediaHub: orchestrates both channels

### Changed
- **CLI Parameters Added**
  - `--neighbor-mode spatial|ring`
  - `--neighbor-radius 3.0` (cells)
  - `--per-agent-depth`
  - `--enable-news-media`
  - `--enable-social-media`
  - `--news-delay 1` (turns)

---

## [2026-01-18] - Task-015 MA System Verification

### Completed
- All 6 verification criteria passed (V1-V6)
- Decision diversity: Shannon entropy > 1.0 ✅
- Behavior rationality: Low-CP expensive < 20% ✅
- Institutional dynamics: Government/Insurance policy changes > 0 ✅

---

## [2026-01-17] - Task-021 Context-Dependent Memory

### Added
- **Contextual Boosters Mechanism**
  - Decoupled design: TieredContextBuilder generates boosters → Memory engine applies them
  - `contextual_boosters` parameter in `memory_engine.retrieve()`
  - Example: `{"emotion:fear": 1.5}` when flood occurs

### Changed
- **Context Builder**
  - New method: `_generate_contextual_boosters(env_context)` in TieredContextBuilder
  - Analyzes environment context and generates tag boosters dynamically

- **Memory Engine**
  - Added `W_context` weight to HumanCentricMemoryEngine
  - Retrieve method now accepts `contextual_boosters` parameter

---

## Known Issues

### Issue-001: Non-ASCII Path Blocker
- **Description**: Gemini CLI cannot execute file operations due to non-ASCII characters in project path
- **Affected**: Gemini CLI agent
- **Workaround**: Use Claude Code or Codex for file operations
- **Status**: Open

### Issue-002: Windows Console Encoding (cp950)
- **Description**: Unicode emoji characters (🔍, ✓, ✗, 💡) cause UnicodeEncodeError
- **Fixed**: Replaced all Unicode with ASCII equivalents in validation scripts
- **Status**: Resolved

---

## File Relocation Checklist (Added 2026-01-21)

When relocating files, follow this checklist to avoid import errors:

- [ ] Physical file move completed
- [ ] Internal imports updated (within moved files)
- [ ] External imports updated (files that import the moved files)
- [ ] Test imports updated (if applicable)
- [ ] Verify all imports: `python -c "from new.path import Module"`
- [ ] Update documentation/README if paths are documented
- [ ] Add artifact entries to `.tasks/artifacts-index.json`
- [ ] Run validation: `python .tasks/scripts/validate_sync.py`

---

## Legend

- **Added**: New features or files
- **Changed**: Changes to existing functionality
- **Deprecated**: Features marked for removal
- **Removed**: Deleted features or files
- **Fixed**: Bug fixes
- **Security**: Security-related changes
