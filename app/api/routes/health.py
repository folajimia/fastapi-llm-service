from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str,str]:
    return {"status": "ok"}

@router.get("/ping")
async def ping():
    return {"status": "coolio"}
