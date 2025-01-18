from fastapi import APIRouter


router = APIRouter()

@router.get('/')
async def root():
    return {"Message":"Hello World,:D"}

@router.get('/{item}')
async def item_name(item:str):
    return {"Message":item}