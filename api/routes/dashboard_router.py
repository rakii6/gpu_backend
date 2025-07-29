from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from firebase_admin import firestore

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

# @router.put('/{user_id}/update')
# async def update_user_profile(request:Request, user_id:str, update_data:dict):
#     print(f"this is the request{request} ")
#     print(f"this is the user_id{user_id} ")
#     print(f"this is the update_data{update_data} ")
    
#     try:
#         if request.state.user_id !=user_id:
#             raise HTTPException(status_code=403, detail="Cannot update other user's profile")
        
#         firebase_serivce = request.state.firebase

#         user_ref = firebase_serivce.db.collection('users').document(user_id)
#         user_ref.update({
#             'name':update_data.get('name'),
#             'phone':update_data.get('phone'),
#             'updated_at':firestore.SERVER_TIMESTAMP
#         })
#         return {
#             "success": True,
#             "message": "Profile updated successfully"
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@router.put('/{user_id}/update')
async def update_user_profile(user_id: str, request: Request):
    """Update user profile information"""
    print(f"this is the request{request}")
    try:
        # Get the request body
        update_data = await request.json()
        print(f"Update request for user {user_id}: {update_data}")
        
        # Verify user can update this profile
        if request.state.user_id != user_id:
            raise HTTPException(status_code=403, detail="Cannot update other user's profile")
        
        firebase_service = request.app.state.firebase
        
        # Update in Firebase
        user_ref = firebase_service.db.collection('users').document(user_id)
        
        # Build update data
        update_fields = {}
        if "name" in update_data:
            update_fields["name"] = update_data["name"]
        if "phone" in update_data:
            update_fields["phone"]= update_data["phone"]
        
        from firebase_admin import firestore
        update_fields["last updated at"]= firestore.SERVER_TIMESTAMP

        user_ref.update(update_fields)
        
        return {
            "success": True,
            "message": "Profile updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")

@router.post('/{user_id}/update_password')
async def update_password(request:Request, user_id:str):

    try:
        if request.state.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
            
        from firebase_admin import auth


        password_data = await request.json()
        current_password = password_data.get('current_password')
        new_password = password_data.get('new_password')
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="Both current and new passwords required")
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        
        user_record = auth.get_user(user_id)
        user_email = user_record.email
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
        
        try:

            import requests
            import os

            firebase_api_key = os.getenv("FIREBASE_API_KEY")
            verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"

            verify_response = requests.post(verify_url, json={
                "email": user_email,
                "password": current_password,
                "returnSecureToken": True
            })
            if verify_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Current password is incorrect")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to verify current password")

        auth.update_user(user_id, password=new_password)
        return {
            "success": True,
            "message": "Password updated successfully"
           
        }
      
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        print(f"Password update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update password")