"""Declarative state transition rules and role authorization for reports.

Strictly enforces:
- An uploader cannot verify or reject their own report.
- Dispute resolution must be performed by an authorized moderator distinct from uploader, verifier, and disputer.
- TTL expiry applies only to eligible states and is executed only by the SYSTEM role.
- Invalid transitions are rejected before any report mutation or audit recording occurs.
"""

from dataclasses import dataclass
from typing import Optional, Set
from streetaccess.verification.models import CommunityReport, ReportState, UserRole


@dataclass(frozen=True)
class TransitionRule:
    from_state: ReportState
    to_state: ReportState
    allowed_roles: Set[UserRole]
    description: str


# Declarative transition matrix
VALID_TRANSITIONS: list[TransitionRule] = [
    TransitionRule(
        from_state=ReportState.SUBMITTED,
        to_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        allowed_roles={UserRole.UPLOADER, UserRole.SYSTEM},
        description="Submitter confirms upload or system automatically queues for review.",
    ),
    TransitionRule(
        from_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        to_state=ReportState.VERIFIED,
        allowed_roles={UserRole.REVIEWER},
        description="Independent community reviewer verifies pedestrian condition.",
    ),
    TransitionRule(
        from_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        to_state=ReportState.REJECTED,
        allowed_roles={UserRole.REVIEWER, UserRole.MODERATOR},
        description="Reviewer or moderator rejects report (e.g. unreadable, irrelevant, spam).",
    ),
    TransitionRule(
        from_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        to_state=ReportState.NEEDS_MORE_EVIDENCE,
        allowed_roles={UserRole.REVIEWER},
        description="Reviewer flags insufficient visual evidence.",
    ),
    TransitionRule(
        from_state=ReportState.NEEDS_MORE_EVIDENCE,
        to_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        allowed_roles={UserRole.UPLOADER},
        description="Uploader attaches requested supplementary evidence.",
    ),
    TransitionRule(
        from_state=ReportState.VERIFIED,
        to_state=ReportState.DISPUTED,
        allowed_roles={UserRole.REVIEWER, UserRole.UPLOADER, UserRole.MODERATOR},
        description="Community member disputes an active verified report.",
    ),
    TransitionRule(
        from_state=ReportState.DISPUTED,
        to_state=ReportState.VERIFIED,
        allowed_roles={UserRole.MODERATOR},
        description="Independent moderator upholds verified status after review.",
    ),
    TransitionRule(
        from_state=ReportState.DISPUTED,
        to_state=ReportState.REJECTED,
        allowed_roles={UserRole.MODERATOR},
        description="Independent moderator overturns report and rejects it.",
    ),
    TransitionRule(
        from_state=ReportState.SUBMITTED,
        to_state=ReportState.EXPIRED,
        allowed_roles={UserRole.SYSTEM},
        description="TTL expiration for unreviewed report.",
    ),
    TransitionRule(
        from_state=ReportState.PENDING_INDEPENDENT_REVIEW,
        to_state=ReportState.EXPIRED,
        allowed_roles={UserRole.SYSTEM},
        description="TTL expiration for unreviewed report.",
    ),
    TransitionRule(
        from_state=ReportState.NEEDS_MORE_EVIDENCE,
        to_state=ReportState.EXPIRED,
        allowed_roles={UserRole.SYSTEM},
        description="TTL expiration when requested evidence is not supplied in time.",
    ),
]


class TransitionValidationResult:
    def __init__(self, is_valid: bool, error_message: Optional[str] = None):
        self.is_valid = is_valid
        self.error_message = error_message


def evaluate_transition(
    report: CommunityReport,
    target_state: ReportState,
    actor_id: str,
    actor_role: UserRole,
) -> TransitionValidationResult:
    """Evaluate whether a proposed transition is declaratively valid and role-authorized.
    
    Returns TransitionValidationResult indicating validity and specific failure reason if invalid.
    """
    # 1. State must actually change
    if report.state == target_state:
        return TransitionValidationResult(
            is_valid=False,
            error_message=f"Report is already in state '{target_state.value}'",
        )

    # 2. Check if the (from_state, to_state) pair exists in declarative transition rules
    matching_rules = [
        r for r in VALID_TRANSITIONS
        if r.from_state == report.state and r.to_state == target_state
    ]

    if not matching_rules:
        return TransitionValidationResult(
            is_valid=False,
            error_message=(
                f"Transition from '{report.state.value}' to '{target_state.value}' "
                "is not permitted by the state transition table."
            ),
        )

    rule = matching_rules[0]

    # 3. Role authorization check
    if actor_role not in rule.allowed_roles:
        allowed = ", ".join(r.value for r in rule.allowed_roles)
        return TransitionValidationResult(
            is_valid=False,
            error_message=(
                f"Role '{actor_role.value}' is not authorized for transition "
                f"'{report.state.value}' -> '{target_state.value}'. Required role in [{allowed}]."
            ),
        )

    # 4. Invariant: Uploader CANNOT verify or reject their own report
    if target_state in (ReportState.VERIFIED, ReportState.REJECTED, ReportState.NEEDS_MORE_EVIDENCE):
        if report.state == ReportState.PENDING_INDEPENDENT_REVIEW and actor_id == report.uploader_id:
            return TransitionValidationResult(
                is_valid=False,
                error_message="Uploader separation violation: uploader cannot verify, reject, or triage their own report.",
            )

    # 5. Invariant: Dispute resolution must be performed by an independent moderator
    if report.state == ReportState.DISPUTED:
        if actor_role != UserRole.MODERATOR:
            return TransitionValidationResult(
                is_valid=False,
                error_message="Only an authorized moderator can resolve disputes.",
            )
        # Moderator must not be uploader, original verifier, or disputer
        conflicts = []
        if actor_id == report.uploader_id:
            conflicts.append("uploader")
        if report.last_verifier_id and actor_id == report.last_verifier_id:
            conflicts.append("prior verifier")
        if report.disputed_by_actor_id and actor_id == report.disputed_by_actor_id:
            conflicts.append("disputer")

        if conflicts:
            conflict_str = ", ".join(conflicts)
            return TransitionValidationResult(
                is_valid=False,
                error_message=f"Dispute resolution conflict of interest: actor is the {conflict_str} of this report.",
            )

    # 6. Expiry check: only SYSTEM role may expire
    if target_state == ReportState.EXPIRED:
        if actor_role != UserRole.SYSTEM:
            return TransitionValidationResult(
                is_valid=False,
                error_message="Only system background workers may perform TTL expiry.",
            )

    return TransitionValidationResult(is_valid=True)

