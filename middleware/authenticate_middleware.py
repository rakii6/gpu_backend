from fastapi import Request
from fastapi.responses import JSONResponse
import firebase_admin
from firebase_admin import auth

async def verify_token(request: Request, call_next):#remember the request:Request handles all the

    public_paths = ['/auth/login','/auth/signup', '/auth/reset-password', '/docs', '/openapi.json']#these 3 lines are to check public paths
    if any (request.url.path.startswith(path) for path in public_paths): 
        return await call_next(request) 
    
    token = request.cookies.get('access_token')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
    if not token:
        return JSONResponse(
            status_code=401,
            content={"status":"Error",
                     "message":"Authentication Required"}
        )
    
    try:
        
        decoded_token = auth.verify_id_token(token)
      

        request.state.user_id = decoded_token['uid']

        return await call_next(request)
    
    except Exception as e:
        return JSONResponse(
            status_code=401,
            content={
                "status":"error",
                "message":"Invalid Authentication Token"
            }
        )