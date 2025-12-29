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
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from core.database_connection import get_db
from review.prompt_improvement_analyzer import PromptImprovementAnalyzer

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


class AnalysisSummary(BaseModel):
    """Summary of an analysis."""
    id: str
    created_at: str
    completed_at: Optional[str]
    status: str
    sandbox_type: str  # Required: 'docker' or 'local' - determines which prompt file to modify
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
    sandbox_type: str  # Required: 'docker' or 'local' - determines which prompt file to modify
    projects_analyzed: List[str]
    num_projects: int  # Count of projects_analyzed array
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
    evidence: dict  # Changed from List[dict] to dict - stores aggregated evidence
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
async def trigger_analysis(request: TriggerAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Trigger a new cross-project prompt improvement analysis.

    Analyzes session patterns across projects to identify
    common issues and generate concrete prompt improvements.

    This now runs in the background to avoid timeouts when using Opus.
    """
    try:
        db = await get_db()

        # Get configured minimum reviews requirement
        from core.config import Config
        config = Config.load_default()
        min_reviews_required = config.review.min_reviews_for_analysis

        # Get project ID - only single project analysis supported
        if not request.project_ids or len(request.project_ids) == 0:
            # Auto-discover first eligible project
            async with db.acquire() as conn:
                # Get projects with sandbox_type matching request
                # that have deep reviews with recommendations in the date range
                query = """
                    SELECT p.id, p.name, COUNT(DISTINCT dr.id) as review_count
                    FROM projects p
                    JOIN sessions s ON s.project_id = p.id
                    JOIN session_deep_reviews dr ON dr.session_id = s.id
                    WHERE (
                        (p.metadata::jsonb->'settings'->>'sandbox_type' = $1)
                        OR (p.metadata::jsonb->'settings' IS NULL AND $1 = 'docker')
                    )
                    AND s.created_at >= NOW() - $2::text::interval
                    AND jsonb_array_length(dr.prompt_improvements) > 0
                    GROUP BY p.id, p.name
                    HAVING COUNT(DISTINCT dr.id) >= $3
                    ORDER BY review_count DESC, p.created_at DESC
                    LIMIT 1
                """

                row = await conn.fetchrow(
                    query,
                    request.sandbox_type,
                    f'{request.last_n_days} days',
                    min_reviews_required
                )

                if not row:
                    return {
                        "success": False,
                        "message": f"No eligible projects found with {min_reviews_required}+ deep reviews in last {request.last_n_days} days"
                    }

                project_id = row['id']
                project_name = row['name']
                logger.info(f"Auto-selected project {project_name} ({project_id}) for analysis")
        else:
            # Use provided project_id (first one if multiple provided)
            try:
                project_id = UUID(request.project_ids[0])
                # Get project name
                async with db.acquire() as conn:
                    project = await conn.fetchrow("SELECT name FROM projects WHERE id = $1", project_id)
                    project_name = project['name'] if project else str(project_id)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid project ID format: {e}"
                )

        # Create analysis record immediately with 'running' status
        from uuid import uuid4
        from datetime import datetime

        analysis_id = uuid4()

        async with db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prompt_improvement_analyses (
                    id,
                    created_at,
                    status,
                    sandbox_type,
                    projects_analyzed,
                    triggered_by,
                    notes
                )
                VALUES ($1, $2, 'running', $3, $4, $5, $6)
                """,
                analysis_id,
                datetime.now(),
                request.sandbox_type,
                [project_id],  # Pass as UUID array
                "manual",
                f"Analyzing project: {project_name}"
            )

        # Run analysis in background
        async def _run_analysis():
            """Background task to run the analysis."""
            try:
                db = await get_db()
                analyzer = PromptImprovementAnalyzer(db)

                logger.info(f"Starting background analysis {analysis_id} for project {project_id}")

                result = await analyzer.analyze_project(
                    project_id=project_id,
                    min_reviews=min_reviews_required,
                    store_in_db=True,
                    triggered_by="manual",
                    analysis_id=analysis_id  # Pass the pre-created ID
                )

                logger.info(f"Completed background analysis {analysis_id}")

                # Send WebSocket notification to project
                from api.main import notify_project_update
                await notify_project_update(str(project_id), {
                    "type": "prompt_improvement_complete",
                    "analysis_id": str(analysis_id),
                    "status": result.get("status", "completed"),
                    "proposals_count": len(result.get("proposals", [])),
                    "message": f"Prompt improvement analysis completed with {len(result.get('proposals', []))} proposals"
                })

            except Exception as e:
                logger.error(f"Failed to run background analysis {analysis_id}: {e}", exc_info=True)
                # Update status to failed
                try:
                    async with db.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE prompt_improvement_analyses
                            SET status = 'failed', completed_at = NOW()
                            WHERE id = $1
                            """,
                            analysis_id
                        )

                    # Send WebSocket notification about failure
                    from api.main import notify_project_update
                    await notify_project_update(str(project_id), {
                        "type": "prompt_improvement_failed",
                        "analysis_id": str(analysis_id),
                        "error": str(e),
                        "message": "Prompt improvement analysis failed"
                    })
                except Exception as update_error:
                    logger.error(f"Failed to update analysis status: {update_error}")

        background_tasks.add_task(_run_analysis)

        return {
            "success": True,
            "message": f"Analysis started for project {project_name}",
            "analysis_id": str(analysis_id),
            "status": "running",
            "note": "This analysis is running in the background. Refresh the page to see results."
        }

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
        analyses = await db.list_prompt_analyses(limit=limit, status=status)

        # Convert to response models
        return [
            AnalysisSummary(
                id=str(a['id']),
                created_at=a['created_at'].isoformat() if a.get('created_at') else None,
                completed_at=a['completed_at'].isoformat() if a.get('completed_at') else None,
                status=a['status'],
                sandbox_type=a['sandbox_type'],  # Required field, no default
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

    except Exception as e:
        logger.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=dict)
async def get_config():
    """
    Get configuration values for the prompt improvement system.

    Returns relevant configuration settings from .yokeflow.yaml.
    """
    try:
        from core.config import Config
        config = Config.load_default()

        return {
            "min_reviews_for_analysis": config.review.min_reviews_for_analysis
        }

    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        # Return default if config fails
        return {
            "min_reviews_for_analysis": 5
        }


@router.get("/metrics", response_model=ImprovementMetrics)
async def get_improvement_metrics():
    """
    Get overall prompt improvement metrics.

    Shows impact of improvements over time.
    """
    try:
        db = await get_db()

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

    except Exception as e:
        logger.error(f"Failed to get improvement metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Proposal-specific routes (MUST come before /{analysis_id}/* routes)
# ============================================================================

@router.patch("/proposals/{proposal_id}", response_model=Proposal)
async def update_proposal_status(
    proposal_id: str,
    request: UpdateProposalRequest
):
    """
    Update proposal status (accept/reject/implement).

    Status values: 'proposed', 'accepted', 'rejected', 'implemented'
    """
    logger.info(f"PATCH /proposals/{proposal_id} - Received proposal_id type={type(proposal_id)}, value={proposal_id}")
    try:
        logger.info(f"Attempting to parse UUID from: {repr(proposal_id)}")
        proposal_uuid = UUID(proposal_id)
        logger.info(f"Successfully parsed UUID: {proposal_uuid}")

        # Validate status
        valid_statuses = ['proposed', 'accepted', 'rejected', 'implemented']
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        db = await get_db()
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

        # Parse evidence if it's a JSON string
        evidence = updated.get('evidence', [])
        if isinstance(evidence, str):
            import json
            try:
                evidence = json.loads(evidence)
            except:
                evidence = []

        return Proposal(
            id=str(updated['id']),
            created_at=updated['created_at'].isoformat(),
            prompt_file=updated['prompt_file'],
            section_name=updated.get('section_name', ''),
            change_type=updated['change_type'],
            original_text=updated.get('original_text', ''),
            proposed_text=updated['proposed_text'],
            rationale=updated['rationale'],
            evidence=evidence,
            confidence_level=updated.get('confidence_level', 5),
            status=updated['status'],
            applied_at=updated['applied_at'].isoformat() if updated.get('applied_at') else None,
            applied_by=updated.get('applied_by')
        )

    except ValueError as ve:
        logger.error(f"ValueError in update_proposal_status: {ve}")
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update proposal {proposal_id}: {e}", exc_info=True)
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

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid proposal ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/generate-diff", response_model=dict)
async def generate_diff(proposal_id: str):
    """
    Generate a precise diff for a proposal using Claude.

    Uses AI to identify specific sections in the prompt file
    and generate exact changes to implement the proposed improvement.
    """
    try:
        from review.diff_generator import generate_diff_for_proposal

        proposal_uuid = UUID(proposal_id)
        db = await get_db()

        # Get proposal details
        proposal = await db.get_prompt_proposal(proposal_uuid)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")

        # Generate diff using Claude
        diff_result = await generate_diff_for_proposal(
            prompt_file=proposal['prompt_file'],
            proposal_text=proposal['proposed_text'],
            rationale=proposal['rationale'],
            section_hint=proposal['section_name']
        )

        # Store diff in database (update proposal with generated_diff field)
        async with db.acquire() as conn:
            await conn.execute(
                """
                UPDATE prompt_proposals
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{generated_diff}',
                    $1::jsonb
                )
                WHERE id = $2
                """,
                json.dumps(diff_result),
                proposal_uuid
            )

        return {
            "success": True,
            "diff": diff_result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate diff for proposal {proposal_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analysis-specific routes
# ============================================================================

@router.get("/{analysis_id}/proposals", response_model=List[Proposal])
async def get_proposals(
    analysis_id: str,
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get all proposals from an analysis.

    Proposals are sorted by confidence level (highest first).
    """
    logger.info(f"get_proposals called with analysis_id={analysis_id} (type: {type(analysis_id)}, repr: {repr(analysis_id)})")
    try:
        logger.info(f"Attempting to parse UUID: {analysis_id}")
        analysis_uuid = UUID(analysis_id)

        logger.info(f"UUID parsed successfully: {analysis_uuid}")
        db = await get_db()
        proposals = await db.list_prompt_proposals(
            analysis_id=analysis_uuid,
            status=status
        )

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

    except ValueError as ve:
        logger.error(f"ValueError parsing UUID '{analysis_id}': {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid analysis ID format: {str(ve)}")
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
        logger.info(f"get_analysis called with analysis_id={analysis_id}")
        analysis_uuid = UUID(analysis_id)
        db = await get_db()
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

        projects_analyzed = [str(pid) for pid in analysis.get('projects_analyzed', [])]

        return AnalysisDetail(
            id=str(analysis['id']),
            created_at=analysis['created_at'].isoformat(),
            completed_at=analysis['completed_at'].isoformat() if analysis.get('completed_at') else None,
            status=analysis['status'],
            sandbox_type=analysis['sandbox_type'],  # Required field - 'docker' or 'local'
            projects_analyzed=projects_analyzed,
            num_projects=len(projects_analyzed),  # Count of projects in the array
            sessions_analyzed=analysis.get('sessions_analyzed', 0),
            patterns_identified=patterns,
            quality_impact_estimate=quality_impact,
            triggered_by=analysis.get('triggered_by', 'unknown'),
            notes=analysis.get('notes')
        )

    except ValueError as ve:
        logger.error(f"ValueError in get_analysis for '{analysis_id}': {ve}")
        raise HTTPException(status_code=400, detail=f"Invalid analysis ID format: {str(ve)}")
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
        # Check if analysis exists
        analysis = await db.get_prompt_analysis(analysis_uuid)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        # Delete the analysis (proposals will cascade)
        await db.delete_prompt_analysis(analysis_uuid)

        return {"success": True, "message": "Analysis deleted successfully"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid analysis ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete analysis {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


