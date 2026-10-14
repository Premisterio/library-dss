"""Reference data for clients: enum codes with Ukrainian labels."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.enums import ENUMS

router = APIRouter(prefix="/meta", tags=["meta"])


class EnumItem(BaseModel):
    code: str
    label: str


class EnumsOut(BaseModel):
    enums: dict[str, list[EnumItem]]


@router.get("/enums", summary="Enum codes with Ukrainian labels")
def get_enums() -> EnumsOut:
    return EnumsOut(
        enums={
            name: [EnumItem(code=code, label=label) for code, label in values.items()]
            for name, values in ENUMS.items()
        }
    )
