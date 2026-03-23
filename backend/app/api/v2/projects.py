"""PROJ-001: Project CRUD endpoints.

GET    /api/v2/projects            — list user's projects (cursor pagination)
POST   /api/v2/projects            — create a project
GET    /api/v2/projects/{id}       — get one project
DELETE /api/v2/projects/{id}       — delete a project
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_async_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectPage, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def _owned_or_404(project: Project | None, user_id: UUID) -> Project:
    if project is None or project.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.get("", response_model=ProjectPage, summary="List the current user's projects")
async def list_projects(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ProjectPage:
    """Return a cursor-paginated list of the authenticated user's projects."""
    # Count total
    count_result = await db.execute(
        select(func.count()).select_from(Project).where(Project.user_id == current_user.id)
    )
    total: int = count_result.scalar_one()

    # Build base query ordered by created_at DESC
    query = (
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        # cursor encodes the last seen created_at ISO string + id (encoded as "ts|id")
        try:
            ts_str, id_str = cursor.split("|", 1)
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(ts_str)
            uid = UUID(id_str)
            query = query.where(
                (Project.created_at < ts)
                | ((Project.created_at == ts) & (Project.id < uid))
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor.")

    result = await db.execute(query)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]

    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"

    return ProjectPage(
        items=[ProjectResponse.model_validate(p) for p in items],
        next_cursor=next_cursor,
        total=total,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ProjectResponse:
    project = Project.create(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        latitude=data.latitude,
        longitude=data.longitude,
        address=data.address,
        polygon_geojson=data.polygon_geojson,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get a project by ID")
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> ProjectResponse:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = _owned_or_404(result.scalar_one_or_none(), current_user.id)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a project",
)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = _owned_or_404(result.scalar_one_or_none(), current_user.id)
    await db.delete(project)
    await db.commit()
