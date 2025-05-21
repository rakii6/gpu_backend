from dotenv import load_dotenv
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
import firebase_admin.exceptions
from pydantic import BaseModel, EmailStr, Field
import firebase_admin
from firebase_admin import auth, firestore
from typing import Optional
import requests
load_dotenv()

API_key = os.getenv("API_KEY")

router = APIRouter(prefix='/auth', tags=["Authentication"])
# 
class SignUpRequest(BaseModel):
    email:EmailStr
    password: str = Field(..., min_length=6)
    name : str


class LoginRequest(BaseModel):
    email:EmailStr
    password: str

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class TokenResponse(BaseModel):
    access_token :str
    token_type:str ='Bearer'
    user_id:str
    name: Optional[str]=None
    email:Optional[str]=None


@router.post('/signup', response_model=TokenResponse)
async def signup(request: SignUpRequest):
    
    """this is for Registration of new account"""
    try:
        try:
            exisiting_user = auth.get_user_by_email(request.email)
            raise HTTPException(
                status_code=400,
                detail="The user with this provided email is already signed-up. Please Log In."
            )
        except firebase_admin.exceptions.FirebaseError:
            user = auth.create_user(
                email = request.email,
                password = request.password,
                display_name = request.name
            )

        user_data = {
            "name":request.name,
            "email":request.email,
            "created_at":firestore.SERVER_TIMESTAMP
        }
        print("creating user in the user collection")
        db = firestore.client()
        user_ref = db.collection('users').document(user.uid)
        user_ref.set(user_data)
        print("user created ")

        print("creating the payment info collection inside the userid")
        payment_info_ref = user_ref.collection('payment_info').document('_info').set({
            "total_count": 0, 
        "initialized_at": firestore.SERVER_TIMESTAMP
        })
        print("done creating payment info collection")
        print("creating the contiainer history collection inside the userid")

        container_history = user_ref.collection('containers').document('_info').set({
    "total_count": 0, 
    "initialized_at": firestore.SERVER_TIMESTAMP
        })
        print("done with creation of the continaer history")

        

        token = auth.create_custom_token(user.uid)
        return{
            "access_token":token.decode('utf-8'),
            "user_id":user.uid,
            "name":request.name,
            "email":request.email
        }
    except Exception as e:
        raise  HTTPException(
            status_code=400,
            detail=str(e)
        )
    

    # try:
    #     user = auth.create_user(
    #         email= request.email,
    #         password = request.password,
    #         display_name = request.name
    #     )
    #     #custom token creation
    #     token = auth.create_custom_token(user.uid)

    #     return TokenResponse(
    #         access_token=token.decode('utf-8'),
    #         user_id=user.uid,
    #         name=request.name,
    #         email=request.email
    #     )
    # except firebase_admin.exceptions.FirebaseError as e:
    #     raise HTTPException(status_code=400, detail=str(e))

def verify_with_email_password(email:EmailStr, password:str):
     
     url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_key}"
     payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
     res=requests.post(url, json=payload)
     if res.status_code == 200:
        return res.json()  # contains idToken, localId, email, etc.
     else:
        raise ValueError("Invalid email or password")

     
# response_model=TokenResponse

@router.post("/login" , response_model=TokenResponse)
async def login(request : LoginRequest, response:Response):

    """Authenticate a login request and send back a response"""

    try: 
        firebase_response = verify_with_email_password(request.email, request.password)
        response.set_cookie(
            key="access_token",
            value=firebase_response["idToken"],
            httponly=True,
            secure=True,
            samesite="lax"
        )
        response.set_cookie(
            key="access_token",
            value=firebase_response["idToken"],
            httponly=True,
            secure=True,
            samesite="lax"
        )

        token_response = TokenResponse(
            access_token=firebase_response["idToken"],
            token_type='Bearer',
            user_id= firebase_response["localId"],
            name=firebase_response["displayName"],
            email=firebase_response["email"]
        )
        return token_response
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except firebase_admin.exceptions.FirebaseError as e:
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
@router.post("/reset-password", status_code=200)
async def reset_password(request : ResetPasswordRequest, response: Response):

    try:
        user =auth.get_user_by_email(request.email)
        reset_link = auth.generate_password_reset_link(request.email)
        
        return{
            "status":f"reset email sent successfully to {request.email}"
        }
        
    except firebase_admin.exceptions.FirebaseError:
        raise HTTPException(
            status_code=404,
            detail="User with this email does not exist"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Something went wrong, try again later"
        )

@router.post("/logout")
async def logout(response:Response):

    try:
        response.delete_cookie(
            key="site",
            httponly=True,
            secure=True,
            samesite="lax"
        )
        return{
            "status":"success",
            "message":"logged out successfully."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f'Logout Failed: {str(e)}'

        )
# @router.get("/validate")
# async def validate_token(request:Request):
#     try:
#         user_id = request.state.user_id #remember the request state is modified by auth middleware, so this user id is globally available. 
#         user = auth.get_user(user_id)
        
#         return{
#                 "status":"success",
#                 "message":"TOken is valid and well",
#                 "user_id":user_id,
#                 "user_details":user,
#             }
#     except Exception as e:
#         return JSONResponse(
#             status_code=500,
#             content={"status": "error from the entire url block", "message": "Invalid token"}
#         )

@router.get("/validate")
async def validate_token(request: Request):
    try:
        # Check if middleware set the user_id
        if not hasattr(request.state, 'user_id'):
            print("No user_id found in request.state - middleware may not be working")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "No user ID found in request state"}
            )
            
        user_id = request.state.user_id
        print(f"User ID found in request state: {user_id}")
        
        # Try to get firebase_service from app state
        if not hasattr(request.app.state, 'firebase'):
            print("No firebase service found in app.state")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "Firebase service not available"}
            )
            
        firebase_service = request.app.state.firebase
        
        # Get user data using a try/except block
        try:
            user_data_response = await firebase_service.get_user(user_id)
            print(f"Firebase get_user response: {user_data_response}")
            
            if user_data_response["status"] == "success":
                user_data = user_data_response["user_data"]
                return {
                    "status": "success",
                    "user_id": user_id,
                    "name": user_data.get("name", ""),
                    "email": user_data.get("email", "")
                }
            else:
                print(f"Error from get_user: {user_data_response}")
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "User not found"}
                )
        except Exception as user_error:
            print(f"Error getting user data: {str(user_error)}")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": f"Error retrieving user data: {str(user_error)}"}
            )
            
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Exception in validate_token: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Server error during token validation",
                "error_details": str(e)
            }
        )
@router.get("/test-token")
async def test_token(request: Request):
    """
    Basic token test that doesn't rely on Firebase services.
    This is useful for isolating whether the issue is with token validation
    or with fetching user data.
    """
    try:
        # Access user_id from request state (set by middleware)
        if hasattr(request.state, 'user_id'):
            user_id = request.state.user_id
            
            # Extract additional info from request state if available
            token_data = {
                "user_id": user_id
            }
            
            # Add any other fields that might be in request.state
            for attr in ['email', 'auth_time', 'email_verified']:
                if hasattr(request.state, attr):
                    token_data[attr] = getattr(request.state, attr)
            
            return {
                "status": "success",
                "message": "Token is valid",
                "token_data": token_data
            }
        else:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "message": "No user ID found in request state"
                }
            )
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"Exception in test_token: {str(e)}")
        print(f"Traceback: {error_traceback}")
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Server error during token test",
                "error_details": str(e)
            }
        )
        
@router.get("/token-debug")
async def token_debug(request: Request):
    """Debugging endpoint to see what's in the request state"""
    
    # Get all attributes from request.state
    state_attrs = {}
    for attr in dir(request.state):
        if not attr.startswith('_'):
            state_attrs[attr] = getattr(request.state, attr)
    
    # Get request headers for debugging
    headers = dict(request.headers)
    auth_header = headers.get('authorization', 'None')
    
    return {
        "status": "debug",
        "request_state": state_attrs,
        "has_user_id": hasattr(request.state, 'user_id'),
        "auth_header": auth_header
    }

@router.post("/verify-specific-token")
async def verify_specific_token(request: Request):
    """
    Manually verify a specific token for debugging
    """
    try:
        token_data = await request.json()
        token = token_data.get("token")
        
        if not token:
            return {"status": "error", "message": "No token provided"}
        
        print(f"Manually verifying token (length: {len(token)})")
        
        try:
            decoded = auth.verify_id_token(token)
            return {
                "status": "success",
                "message": "Token verified successfully",
                "decoded": decoded
            }
        except Exception as e:
            print(f"Manual verification error: {str(e)}")
            return {
                "status": "error",
                "message": f"Token verification failed: {str(e)}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Request processing error: {str(e)}"}
    
@router.get("/verify-token-test")
async def verify_token_test(request: Request):
    """
    Test endpoint that requires authentication
    """
    if hasattr(request.state, 'user_id'):
        user_id = request.state.user_id
        
        # Get user from Firebase
        try:
            user = auth.get_user(user_id)
            return {
                "status": "success",
                "message": "Token is valid",
                "user_id": user_id,
                "email": user.email,
                "display_name": user.display_name
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error retrieving user details: {str(e)}",
                "user_id": user_id
            }
    else:
        return {
            "status": "error",
            "message": "No user ID found in request state - token validation failed"
        }