"""
Prompt Improvement API Routes
==============================

API endpoints for the prompt improvement system.
Handles cross-project analysis and prompt proposal management.

Created: December 21, 2025
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from database_connection import get_db
from prompt_improvement_analyzer import PromptImprovementAnalyzer

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/prompt-improvements", tags=["prompt-improvements"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TriggerAnalysisRequest(BaseModel):
    """Request body for triggering a new analysis."""
    project_ids: Optional[List[str]] = Field(
        None,
        description="Specific projects to analyze (None = all eligible)"
    )
    sandbox_type: str = Field(
        "docker",
        description="Which prompt to improve: 'docker' or 'local'"
    )
    last_n_days: int = Field(
        7,
        description="Only analyze sessions from last N days",
        ge=1,
        le=90
    )
    min_sessions_per_project: int = Field(
        5,
        description="Minimum sessions required per project",
        ge=1
    )


class AnalysisSummary(BaseModel):
    """Summary of an analysis."""
    id: str
    created_at: str
    completed_at: Optional[str]
    status: str
    sandbox_type: str
    num_projects: int
    sessions_analyzed: int
    quality_impact_estimate: Optional[float]
    total_proposals: int
    pending_proposals: int
    accepted_proposals: int
    implemented_proposals: int


class AnalysisDetail(BaseModel):
    """Detailed analysis with patterns."""
    id: str
    created_at: str
    completed_at: Optional[str]
    status: str
    sandbox_type: str
    projects_analyzed: List[str]
    sessions_analyzed: int
    patterns_identified: dict
    quality_impact_estimate: Optional[float]
    triggered_by: str
    notes: Optional[str]


class Proposal(BaseModel):
    """Prompt change proposal."""
    id: str
    created_at: str
    prompt_file: str
    section_name: str
    change_type: str
    original_text: str
    proposed_text: str
    rationale: str
    evidence: List[dict]
    confidence_level: int
    status: str
    applied_at: Optional[str]
    applied_by: Optional[str]


class UpdateProposalRequest(BaseModel):
    """Request to update proposal status."""
    status: str = Field(
        ...,
        description="New status: 'accepted', 'rejected', or 'implemented'"
    )
    notes: Optional[str] = None


class ApplyProposalResponse(BaseModel):
    """Response from applying a proposal."""
    success: bool
    message: str
    git_commit_hash: Optional[str]
    version_id: Optional[str]


class PromptVersion(BaseModel):
    """Prompt version information."""
    id: str
    created_at: str
    prompt_file: str
    version_name: str
    git_commit_hash: Optional[str]
    changes_summary: Optional[str]
    is_active: bool
    is_default: bool
    projects_using: int
    avg_quality_rating: Optional[float]
    total_sessions: int


class ImprovementMetrics(BaseModel):
    """Overall improvement metrics."""
    total_analyses: int
    total_proposals: int
    accepted_proposals: int
    implemented_proposals: int
    avg_quality_improvement: float
    most_common_issues: List[dict]


# =============================================================================
# Endpoints
# =============================================================================

@router.post("", response_model=dict)
async def trigger_analysis(request: TriggerAnalysisRequest):
    """
    Trigger a new cross-project prompt improvement analysis.

    Analyzes session patterns across projects to identify
    common issues and generate concrete prompt improvements.
    """
    try:
        db = await get_db()
        try:
            analyzer = PromptImprovementAnalyzer(db)

            # Convert string project IDs to UUIDs
            project_ids = None
            if request.project_ids:
                try:
                    project_ids = [UUID(pid) for pid in request.project_ids]
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid project ID format: {e}"
                    )

            # Run analysis
            result = await analyzer.analyze_projects(
                project_ids=project_ids,
                sandbox_type=request.sandbox_type,
                last_n_days=request.last_n_days,
                min_sessions_per_project=request.min_sessions_per_project,
                triggered_by="manual"
            )

            return result

        finally:
            await db.disconnect()

    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[AnalysisSummary])
async def list_analyses(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, description="Maximum number to return", ge=1, le=100)
):
    """
    List all prompt improvement analyses.

    Returns summaries with proposal counts.
    """
    try:
        db = await get_db()
        try:
            analyses = await db.list_prompt_analyses(limit=limit, status=status)

            # Convert to response models
            return [
                AnalysisSummary(
                    id=str(a['id']),
                    created_at=a['created_at'].isoformat() if a.get('created_at') else None,
                    completed_at=a['completed_at'].isoformat() if a.get('completed_at') else None,
                    status=a['status'],
                    sandbox_type=a.get('sandbox_type', 'docker'),
                    num_projects=a.get('num_projects', 0),
                    sessions_analyzed=a.get('sessions_analyzed', 0),
                    quality_impact_estimate=float(a['quality_impact_estimate']) if a.get('quality_impact_estimate') else None,
                    total_proposals=a.get('total_proposals', 0),
                    pending_proposals=a.get('pending_proposals', 0),
                    accepted_proposals=a.get('accepted_proposals', 0),
                    implemented_proposals=a.get('implemented_proposals', 0)
                )
                for a in analyses
            ]

        finally:
            await db.disconnect()

    except Exception as e:
        logger.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=ImprovementMetrics)
async def get_improvement_metrics():
    """
    Get overall prompt improvement metrics.

    Shows impact of improvements over time.
    """
    try:
        db = await get_db()
        try:
            # Get all analyses
            analyses = await db.list_prompt_analyses(limit=100)

            # Get all proposals
            proposals = await db.list_prompt_proposals(limit=500)

            # Calculate metrics
            total_analyses = len(analyses)
            total_proposals = len(proposals)
            accepted_proposals = sum(1 for p in proposals if p['status'] == 'accepted')
            implemented_proposals = sum(1 for p in proposals if p['status'] == 'implemented')

            # Calculate average quality improvement
            completed_analyses = [a for a in analyses if a.get('status') == 'completed']
            avg_improvement = 0.0
            if completed_analyses:
                improvements = [
                    float(a.get('quality_impact_estimate', 0))
                    for a in completed_analyses
                    if a.get('quality_impact_estimate')
                ]
                avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0

            # Find most common issues
            issue_counts = {}
            for analysis in completed_analyses:
                patterns = analysis.get('patterns_identified', {})
                for issue in patterns.get('issues', []):
                    issue_type = issue.get('type', 'unknown')
                    if issue_type not in issue_counts:
                        issue_counts[issue_type] = {
                            'type': issue_type,
                            'count': 0,
                            'severity': issue.get('severity', 'unknown')
                        }
                    issue_counts[issue_type]['count'] += 1

            most_common = sorted(
                issue_counts.values(),
                key=lambda x: x['count'],
                reverse=True
            )[:5]

            return ImprovementMetrics(
                total_analyses=total_analyses,
                total_proposals=total_proposals,
                accepted_proposals=accepted_proposals,
                implemented_proposals=implemented_proposals,
                avg_quality_improvement=avg_improvement,
                most_common_issues=most_common
            )

        finally:
            await db.disconnect()

    except Exception as e:
        logger.error(f"Failed to get improvement metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions", response_model=List[PromptVersion])
async def list_prompt_versions(
    prompt_file: str = Query(..., description="Prompt file name")
):
    """
    List all versions of a prompt file.

    Returns version history with performance metrics.
    """
    try:
        db = await get_db()
        try:
            versions = await db.get_prompt_versions(prompt_file, limit=50)

            return [
                PromptVersion(
                    id=str(v['id']),
                    created_at=v['created_at'].isoformat(),
                    prompt_file=v['prompt_file'],
                    version_name=v['version_name'],
                    git_commit_hash=v.get('git_commit_hash'),
                    changes_summary=v.get('changes_summary'),
                    is_active=v.get('is_active', False),
                    is_default=v.get('is_default', False),
                    projects_using=v.get('projects_using', 0),
                    avg_quality_rating=float(v['avg_quality_rating']) if v.get('avg_quality_rating') else None,
                    total_sessions=v.get('total_sessions', 0)
                )
                for v in versions
            ]

        finally:
            await db.disconnect()

    except Exception as e:
        logger.error(f"Failed to list prompt versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{analysis_id}/proposals", response_model=List[Proposal])
async def get_proposals(
    analysis_id: str,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get all proposals from an analysis.

    Proposals are sorted by confidence level (highest first).
    """
    print(f"!!! get_proposals called with analysis_id={analysis_id} !!!")
    logger.info(f"get_proposals called with analysis_id={analysis_id}")
    try:
        print(f"!!! Attempting UUID parse !!!")
        logger.info(f"Attempting to parse UUID: {analysis_id}")
        analysis_uuid = UUID(analysis_id)
        print(f"!!! UUID parsed successfully: {analysis_uuid} !!!")
        logger.info(f"UUID parsed successfully: {analysis_uuid}")
        db = await get_db()
        try:
            proposals = await db.list_prompt_proposals(
                analysis_id=analysis_uuid,
                status=status
            )
            print(f"!!! Found {len(proposals)} proposals !!!")
            if proposals:
                print(f"!!! First proposal keys: {list(proposals[0].keys())} !!!")
                print(f"!!! Evidence type: {type(proposals[0].get('evidence'))} !!!")
                print(f"!!! Evidence value: {proposals[0].get('evidence')} !!!")

            result = []
            for p in proposals:
                # Parse evidence if it's a JSON string
                evidence = p.get('evidence', [])
                if isinstance(evidence, str):
                    import json
                    try:
                        evidence = json.loads(evidence)
                    except:
                        evidence = []

                print(f"!!! Creating Proposal with evidence type: {type(evidence)} !!!")
                result.append(Proposal(
                    id=str(p['id']),
                    created_at=p['created_at'].isoformat(),
                    prompt_file=p['prompt_file'],
                    section_name=p.get('section_name', ''),
                    change_type=p['change_type'],
                    original_text=p.get('original_text', ''),
                    proposed_text=p['proposed_text'],
                    rationale=p['rationale'],
                    evidence=evidence,
                    confidence_level=p.get('confidence_level', 5),
                    status=p['status'],
                    applied_at=p['applied_at'].isoformat() if p.get('applied_at') else None,
                    applied_by=p.get('applied_by')
                ))

            return result

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid analysis ID format")
    except Exception as e:
        logger.error(f"Failed to get proposals for analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{analysis_id}", response_model=AnalysisDetail)
async def get_analysis(analysis_id: str):
    """
    Get detailed analysis information.

    Includes identified patterns and proposals.
    """
    try:
        analysis_uuid = UUID(analysis_id)
        db = await get_db()
        try:
            analysis = await db.get_prompt_analysis(analysis_uuid)

            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")

            # Parse patterns_identified if it's a JSON string
            patterns = analysis.get('patterns_identified', {})
            if isinstance(patterns, str):
                import json
                try:
                    patterns = json.loads(patterns)
                except:
                    patterns = {}

            # Convert quality_impact_estimate to float
            quality_impact = analysis.get('quality_impact_estimate')
            if quality_impact is not None:
                quality_impact = float(quality_impact)

            return AnalysisDetail(
                id=str(analysis['id']),
                created_at=analysis['created_at'].isoformat(),
                completed_at=analysis['completed_at'].isoformat() if analysis.get('completed_at') else None,
                status=analysis['status'],
                sandbox_type=analysis['sandbox_type'],
                projects_analyzed=[str(pid) for pid in analysis.get('projects_analyzed', [])],
                sessions_analyzed=analysis.get('sessions_analyzed', 0),
                patterns_identified=patterns,
                quality_impact_estimate=quality_impact,
                triggered_by=analysis.get('triggered_by', 'unknown'),
                notes=analysis.get('notes')
            )

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid analysis ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.delete("/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """
    Delete a prompt improvement analysis and all its proposals.

    This is a cascading delete - all proposals associated with this analysis
    will also be deleted.
    """
    try:
        analysis_uuid = UUID(analysis_id)
        db = await get_db()
        try:
            # Check if analysis exists
            analysis = await db.get_prompt_analysis(analysis_uuid)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")

            # Delete the analysis (proposals will cascade)
            await db.delete_prompt_analysis(analysis_uuid)

            return {"success": True, "message": "Analysis deleted successfully"}

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid analysis ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/proposals/{proposal_id}", response_model=Proposal)
async def update_proposal_status(
    proposal_id: str,
    request: UpdateProposalRequest
):
    """
    Update proposal status (accept/reject/implement).

    Status values: 'proposed', 'accepted', 'rejected', 'implemented'
    """
    try:
        proposal_uuid = UUID(proposal_id)

        # Validate status
        valid_statuses = ['proposed', 'accepted', 'rejected', 'implemented']
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        db = await get_db()
        try:
            # Get current proposal
            proposal = await db.get_prompt_proposal(proposal_uuid)
            if not proposal:
                raise HTTPException(status_code=404, detail="Proposal not found")

            # Update status
            await db.update_prompt_proposal_status(
                proposal_uuid,
                request.status
            )

            # Get updated proposal
            updated = await db.get_prompt_proposal(proposal_uuid)

            return Proposal(
                id=str(updated['id']),
                created_at=updated['created_at'].isoformat(),
                prompt_file=updated['prompt_file'],
                section_name=updated.get('section_name', ''),
                change_type=updated['change_type'],
                original_text=updated.get('original_text', ''),
                proposed_text=updated['proposed_text'],
                rationale=updated['rationale'],
                evidence=updated.get('evidence', []),
                confidence_level=updated.get('confidence_level', 5),
                status=updated['status'],
                applied_at=updated['applied_at'].isoformat() if updated.get('applied_at') else None,
                applied_by=updated.get('applied_by')
            )

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/apply", response_model=ApplyProposalResponse)
async def apply_proposal(proposal_id: str):
    """
    Apply a proposal to the actual prompt file.

    This will:
    1. Create a backup of the current prompt
    2. Apply the change
    3. Create a git commit
    4. Mark proposal as 'implemented'

    NOTE: This endpoint is not yet fully implemented.
    For now, it only updates the proposal status.
    """
    try:
        proposal_uuid = UUID(proposal_id)
        db = await get_db()
        try:
            proposal = await db.get_prompt_proposal(proposal_uuid)
            if not proposal:
                raise HTTPException(status_code=404, detail="Proposal not found")

            if proposal['status'] != 'accepted':
                raise HTTPException(
                    status_code=400,
                    detail="Proposal must be 'accepted' before applying"
                )

            # TODO: Implement actual file modification and git commit
            # For now, just mark as implemented
            await db.update_prompt_proposal_status(
                proposal_uuid,
                'implemented',
                applied_by='system',
                applied_to_version='pending'
            )

            return ApplyProposalResponse(
                success=True,
                message="Proposal marked as implemented (manual file changes required)",
                git_commit_hash=None,
                version_id=None
            )

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/versions/{version_id}/activate")
async def activate_version(version_id: str):
    """
    Set a prompt version as the active default.

    Deactivates all other versions of the same file.
    """
    try:
        version_uuid = UUID(version_id)
        db = await get_db()
        try:
            # Get version to find prompt file
            version = await db.get_prompt_versions(prompt_file="", limit=1000)
            target_version = next((v for v in version if str(v['id']) == version_id), None)

            if not target_version:
                raise HTTPException(status_code=404, detail="Version not found")

            # Activate it
            await db.set_active_prompt_version(
                version_uuid,
                target_version['prompt_file']
            )

            return {"success": True, "message": "Version activated"}

        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid version ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate version {version_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
