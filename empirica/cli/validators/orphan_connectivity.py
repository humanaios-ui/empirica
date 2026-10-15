"""
Orphan Connectivity Validator — Phase 3 CLI Enhancement

Validates that all logged artifacts (findings, unknowns, assumptions, decisions) have
≥1 edge to related artifacts, OR explicitly document why no edges exist.

Usage:
    from orphan_connectivity_validator import validate_artifact_connectivity
    
    # Validate a finding with edges
    validate_artifact_connectivity(
        artifact_type='finding',
        claim_text='...',
        edge_targets=['<uuid1>', '<uuid2>'],
        reason_no_edges=None,
        enforce=True
    )
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class ArtifactType(Enum):
    FINDING = "finding"
    UNKNOWN = "unknown"
    ASSUMPTION = "assumption"
    DECISION = "decision"
    DEAD_END = "dead_end"
    MISTAKE = "mistake"


class ConnectivityValidationError(Exception):
    """Raised when artifact connectivity validation fails."""
    pass


@dataclass
class ConnectivityValidationResult:
    """Result of a connectivity validation check."""
    valid: bool
    message: str
    artifact_id: Optional[str] = None
    edge_count: int = 0
    has_reason_no_edges: bool = False


def validate_artifact_connectivity(
    artifact_type: str,
    claim_text: str,
    edge_targets: Optional[List[str]] = None,
    reason_no_edges: Optional[str] = None,
    artifact_id: Optional[str] = None,
    enforce: bool = True
) -> ConnectivityValidationResult:
    """
    Validate that an artifact has sufficient connectivity or explicit documentation.

    Phase 3 requirement: All artifacts must either:
    1. Have ≥1 edge_target (link to related artifacts), OR
    2. Have a reason_no_edges explanation (why no edges yet)

    Args:
        artifact_type: Type of artifact (finding, unknown, assumption, decision, etc.)
        claim_text: The artifact's claim/content
        edge_targets: List of UUIDs of related artifacts to link to
        reason_no_edges: Explanation for why no edges exist
        artifact_id: UUID of the artifact being validated (for logging)
        enforce: If True, raise ConnectivityValidationError on validation failure

    Returns:
        ConnectivityValidationResult with validation status and message

    Raises:
        ConnectivityValidationError: If enforce=True and validation fails
    """
    
    # Normalize inputs
    edge_targets = edge_targets or []
    reason_no_edges = (reason_no_edges or "").strip()
    
    # Count edges
    edge_count = len([t for t in edge_targets if t and t.strip()])
    has_reason = len(reason_no_edges) > 0
    
    # Validation logic
    is_valid = edge_count > 0 or has_reason
    
    # Build message
    if is_valid:
        if edge_count > 0:
            message = f"✓ Artifact connected: {edge_count} edge(s)"
        else:
            message = f"✓ Artifact documented: reason_no_edges provided ({len(reason_no_edges)} chars)"
    else:
        message = (
            f"✗ Artifact has no connectivity:\n"
            f"  - No edges provided (required: ≥1)\n"
            f"  - No reason_no_edges provided (required if edges=0)\n"
            f"  Use one of:\n"
            f"    --edge ID:RELATION  or  --related-to ID   (repeatable)\n"
            f"    --reason-no-edges 'explanation why no edges yet'"
        )
    
    result = ConnectivityValidationResult(
        valid=is_valid,
        message=message,
        artifact_id=artifact_id,
        edge_count=edge_count,
        has_reason_no_edges=has_reason
    )
    
    if not is_valid and enforce:
        raise ConnectivityValidationError(message)
    
    return result


def validate_batch_artifacts(artifacts: List[dict], enforce: bool = True) -> dict:
    """Validate connectivity for multiple artifacts in a batch operation."""
    
    results = []
    failures = []
    
    for artifact in artifacts:
        result = validate_artifact_connectivity(
            artifact_type=artifact.get('artifact_type'),
            claim_text=artifact.get('claim_text', ''),
            edge_targets=artifact.get('edge_targets'),
            reason_no_edges=artifact.get('reason_no_edges'),
            artifact_id=artifact.get('artifact_id'),
            enforce=enforce
        )
        
        results.append(result)
        
        if not result.valid:
            failures.append({
                'artifact_id': result.artifact_id,
                'artifact_type': artifact.get('artifact_type'),
                'message': result.message
            })
    
    return {
        'valid_count': sum(1 for r in results if r.valid),
        'invalid_count': sum(1 for r in results if not r.valid),
        'results': results,
        'failures': failures
    }


def format_cli_error(validation_result: ConnectivityValidationResult) -> str:
    """Format a validation error for CLI output."""
    return f"❌ finding-log: {validation_result.message}"
