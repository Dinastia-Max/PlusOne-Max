from typing import Annotated

from fastapi import Header


async def get_current_user_id(
    user_id: Annotated[int, Header(alias="X-User-Id", gt=0)],
) -> int:
    return user_id
