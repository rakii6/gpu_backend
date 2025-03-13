from fastapi import APIRouter, Depends, HTTPException, Request, Response
import firebase_admin.exceptions
from pydantic import BaseModel, EmailStr, Field
import firebase_admin
from firebase_admin import auth, firestore
from typing import Optional

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
            "created_at":firestore.SERVER_TIMESTAMP,
            'payment_info':None
        }
    
        db = firestore.client()
        db.collection('users').document(user.uid).set(user_data)
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

@router.post("/login", response_model=TokenResponse)
async def login(request : LoginRequest, response:Response):

    """Authenticate a login request and send back a response"""

    try:
        user = auth.get_user_by_email(request.email)

        token = auth.create_custom_token(user.uid)

        response.set_cookie(
            key="access_token",
            value=token.decode('utf-8'),
            httponly=True,
            secure=True,
            samesite="lax"
        )
        return TokenResponse(
            access_token=token.decode('utf-8'),
            user_id=user.uid,
            name=user.display_name,
            email=user.email
        )
    except firebase_admin.exceptions.FirebaseError as e:
        raise HTTPException(status_code=401, detail="Invail Credentials")
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

