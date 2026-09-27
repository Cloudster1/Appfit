import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from appfit.auth.deps import require_editor, require_viewer
from appfit.db.engine import get_db
from appfit.models import App, Tag, TagCategory, User, app_tags
from appfit.schemas.app import TagCreate, TagOut, TagUpdate
from appfit.services.apps import get_or_create_tag, sync_derived
from appfit.services.errors import ConflictError, NotFoundError, ServiceError

router = APIRouter(prefix="/tags", tags=["tags"])


def _tag_out(db: Session, tag: Tag) -> TagOut:
    count = db.scalar(select(func.count()).select_from(app_tags).where(app_tags.c.tag_id == tag.id)) or 0
    return TagOut(id=tag.id, name=tag.name, category=tag.category, app_count=count)


def _apps_with_tag(db: Session, tag_id: uuid.UUID) -> list[App]:
    return list(db.scalars(select(App).where(App.tags.any(Tag.id == tag_id))).all())


@router.get("", response_model=list[TagOut])
def list_tags(
    category: TagCategory | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> list[TagOut]:
    count = func.count(app_tags.c.app_id).label("app_count")
    stmt = (
        select(Tag, count)
        .outerjoin(app_tags, app_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.category, Tag.name)
    )
    if category is not None:
        stmt = stmt.where(Tag.category == category)
    return [TagOut(id=t.id, name=t.name, category=t.category, app_count=n) for t, n in db.execute(stmt).all()]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(body: TagCreate, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> TagOut:
    tag = get_or_create_tag(db, body.name.strip().lower(), body.category)
    db.commit()
    return _tag_out(db, tag)


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: uuid.UUID, body: TagUpdate, db: Session = Depends(get_db), _: User = Depends(require_editor)
) -> TagOut:
    """Rename a tag, or merge it into another tag of any category (apps are re-indexed)."""
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("Tag not found")
    affected = _apps_with_tag(db, tag.id)
    if body.merge_into is not None:
        target = db.get(Tag, body.merge_into)
        if target is None or target.id == tag.id:
            raise ServiceError("Invalid merge target")
        for app in affected:
            app.tags = [t for t in app.tags if t.id != tag.id] + ([] if target in app.tags else [target])
        db.flush()
        db.delete(tag)
        result = target
    elif body.name is not None:
        name = body.name.strip().lower()
        clash = db.scalar(select(Tag.id).where(Tag.category == tag.category, Tag.name == name, Tag.id != tag.id))
        if clash is not None:
            raise ConflictError("A tag with this name already exists; merge instead")
        tag.name = name
        result = tag
    else:
        return _tag_out(db, tag)
    for app in affected:
        sync_derived(db, app)
    db.commit()
    return _tag_out(db, result)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_editor)) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("Tag not found")
    affected = _apps_with_tag(db, tag.id)
    for app in affected:
        app.tags = [t for t in app.tags if t.id != tag.id]
    db.flush()
    db.delete(tag)
    for app in affected:
        sync_derived(db, app)
    db.commit()
