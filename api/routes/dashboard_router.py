from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/profile", tags=["Profile"])

class CreateProfileRequest(BaseModel):
    user_id:str
    email:str
    name:str=""


@router.post('/initialze')
async def init_user_profile(request_data:CreateProfileRequest, request:Request):
    
    user_profile_service = request.app.state.user_profile

    result = await user_profile_service.initialize_user(
        user_id=request_data.user_id,
        email=request_data.email,
      

    )
    if result["status"]=="error":
        raise HTTPException(status_code=500, detail="Failed to init user profile")
    return result
@router.get('/{user_id}')
async def get_user_profile(user_id:str, request:Request):
    
    user_profile_service = request.app.state.user_profile
    result = await user_profile_service.get_user_profile(user_id)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
        
    return result