# Task-058A: Structured Artifact Protocols

Status: ? Complete (Codex)
Commit: 21dbf5b

Summary
- Added structured artifacts and validation for MA communication:
  - PolicyArtifact
  - MarketArtifact
  - HouseholdIntention
  - ArtifactEnvelope (to AgentMessage)
- Tests added: tests/test_artifacts.py

Verification
- pytest tests/test_artifacts.py -v

Notes
- ArtifactEnvelope now adapts to AgentMessage schema (sender_id/sender_type/timestamp).
- Added compatibility attributes: sender, step for legacy expectations.
