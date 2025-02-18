from fastapi import APIRouter


router = APIRouter()

@router.get('/')
async def root():
    try:
        return{"Message":"Hello World :D"}
    except Exception as e:
        print(f"error in root endpoint: {str(e)}")
        return{"statut":"error",
               "message":str(e)}

@router.get('/{item}')
async def item_name(item:str):
    return {"Message":item}