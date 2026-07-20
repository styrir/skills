"""Rejection and review codes (plan §5.4)."""

from __future__ import annotations

REJECTION_CODES = frozenset({
    "PROFILE_REQUIRED_FOR_REVISION",
    "UNENFORCEABLE_PROFILE_HYPOTHESIS",
    "LOW_CONFIDENCE_PROPOSAL",
    "MODEL_REQUESTED_REVIEW",
    "MALFORMED_EDIT_PROPOSAL",
    "EDIT_TARGET_NOT_FOUND",
    "EDIT_TARGET_AMBIGUOUS",
    "PREPARED_STATE_MISMATCH",
    "CONSENT_INVALID",
    "CONSENT_BACKEND_MISMATCH",
    "BACKEND_RESOLUTION_REQUIRED",
    "SOURCE_HASH_MISMATCH",
    "PASSAGE_HASH_MISMATCH",
    "EDIT_RANGE_INVALID",
    "EDIT_OVERLAP",
    "PROTECTED_SPAN_OVERLAP",
    "SENTINEL_BOUNDARY_VIOLATION",
    "SENTINEL_MISSING",
    "SENTINEL_DUPLICATED",
    "SENTINEL_ORDER_CHANGED",
    "PROTECTED_CONTENT_CHANGED",
    "UNVERIFIED_TOKEN_CHANGE",
    "UNVERIFIED_ENTITY_CHANGE",
    "PATTERN_EVIDENCE_MISMATCH",
    "PATTERN_EVIDENCE_INSUFFICIENT",
    "CORPUS_ATTESTED_PATTERN",
    "CONTEXTUAL_PATTERN_NOT_CONFIRMED",
    "CONTEXTUAL_PATTERN_UNCERTAIN",
    "PROFILE_MEMORIZATION_OVERLAP",
    "REVIEW_APPROVAL_INVALID",
    "SEMANTIC_DRIFT",
    "REGISTER_FLATTENING",
    "UNSUPPORTED_FACT",
    "EDIT_OUTSIDE_AUTHORIZED_SCOPE",
})

REASON_CATEGORIES = frozenset({
    "voice_drift",
    "formulaic_ai_residue",
    "clarity",
    "redundancy",
    "user_requested",
})

MODES = frozenset({
    "conservative",
    "high-register",
    "technical",
    "diagnose-only",
})

SCHEMA_VERSIONS = {
    "edit-proposal": "edit-proposal.v1",
    "edit-set": "edit-set.v1",
    "voice-audit": "voice-audit.v1",
    "voice-review-approval": "voice-review-approval.v1",
    "voice-consent": "voice-consent.v1",
    "route-resolution": "route-resolution.v1",
    "prepared-state": "prepared-state.v1",
    "handoff-manifest": "handoff-manifest.v1",
}

CONFIDENCE_REVIEW_THRESHOLD = 0.80
