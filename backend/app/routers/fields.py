from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Field
from app.schemas import FieldResponse


router = APIRouter(prefix="/fields", tags=["fields"])


@router.get("", response_model=list[FieldResponse])
async def get_fields(
    session: AsyncSession = Depends(get_db),
) -> list[FieldResponse]:
    result = await session.scalars(
        select(Field)
        .where(Field.is_active.is_(True))
        .order_by(Field.name, Field.id)
    )
    return [FieldResponse.model_validate(field) for field in result.all()]
