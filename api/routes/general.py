from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
import GPUtil
import asyncio
router = APIRouter()

@router.get('/')
async def root():
    try:
        return{"Message":"Hello World :D",
               "Description 1":"Thanks for landing here, just a student, trying to build and design something for everyone to use."}
    except Exception as e:
        print(f"error in root endpoint: {str(e)}")
        return{"statut":"error",
               "message":str(e)}

# @router.get('/{item}')
# async def item_name(item:str):
#     return {"Message":item}
@router.get('/get-container-of-user/{user_id}')
async def get_user_containers(user_id, request:Request):
    firebase_service=request.app.state.firebase
    return await firebase_service.get_users_containers(user_id)




    



