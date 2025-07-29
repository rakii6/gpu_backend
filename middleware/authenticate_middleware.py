from fastapi import Request
from fastapi.responses import JSONResponse
import firebase_admin
from firebase_admin import auth

async def verify_token(request: Request, call_next):#remember the request:Request handles all the

    public_paths = ['/auth/login','/auth/signup', '/auth/reset-password', '/docs', '/openapi.json', 'docker/test-persistence/test123']#these 3 lines are to check public paths
    if any (request.url.path.startswith(path) for path in public_paths): 
        return await call_next(request) 
    
    token = request.cookies.get('site')
    if not token:
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
            print("the token is ",token)
    if not token:
        return JSONResponse(
            status_code=401,
            content={"status":"Error",
                     "message":"Authentication Required"}
        )
    
    try:
        print(f"attemping to verify the token  {token[:10]}...")
        decoded_token = auth.verify_id_token(token)
        
        print(f"Token is verified")
        

        request.state.user_id = decoded_token['uid'] #this is a curcial part, this middleware sets the global userid, for that current user, 
        #This  user id ready to be used or summon anywhere in the platform simpley -> request.state.user_id
        print(request.state) 
        # request.state.email = decoded_token.get('email')
        # request.state.aut_time = decoded_token.get('auth_time')


        return await call_next(request)
    
    except Exception as e:
       
        return JSONResponse(
            status_code=401,
            content={
                "status":"error",
                "message":"Invalid Authentication Token"
            }
        )


# from fastapi import Request
# from fastapi.responses import JSONResponse
# import firebase_admin
# from firebase_admin import auth
# import time
# import traceback

# async def verify_token(request: Request, call_next):
#     # Define exact public paths - note the more specific matching pattern
#     public_paths = ['/auth/login', '/auth/signup', '/auth/reset-password', '/docs', '/openapi.json', '/']

#     # Check if the path is exactly in the public paths list
#     if request.url.path in public_paths:
#         print(f"Skipping auth for exact public path match: {request.url.path}")
#         return await call_next(request)
    
#     # Special case for docs and openapi paths that may have query params
#     if request.url.path.startswith('/docs/') or request.url.path.startswith('/openapi'):
#         print(f"Skipping auth for docs/openapi path: {request.url.path}")
#         return await call_next(request)
    
#     # Debug paths - consider removing these in production
#     if request.url.path in ['/auth/token-debug']:
#         print(f"Skipping auth for debug path: {request.url.path}")
#         return await call_next(request)
    
#     # For all other paths, require authentication
#     token = request.cookies.get('site')
#     token_source = "cookie"
    
#     if not token:
#         auth_header = request.headers.get('Authorization')
#         if auth_header and auth_header.startswith('Bearer '):
#             token = auth_header.replace('Bearer ', '')
#             token_source = "header"
#             print(f"Found token in Authorization header (length: {len(token)})")
    
#     if not token:
#         print("No token found in cookies or Authorization header")
#         return JSONResponse(
#             status_code=401,
#             content={"status": "error", "message": "Authentication Required"}
#         )
    
#     print(f"Verifying token from {token_source} (length: {len(token)})")
    
#     try:
#         # Verify the token
#         decoded_token = auth.verify_id_token(token)
        
#         print(f"Token verified successfully! User ID: {decoded_token.get('uid')}")
        
#         # Store user_id in request state
#         request.state.user_id = decoded_token.get('uid')
        
#         # Continue processing the request
#         return await call_next(request)
        
#     except Exception as e:
#         import traceback
#         error_trace = traceback.format_exc()
#         print(f"Token verification failed: {str(e)}")
#         print(f"Error trace: {error_trace}")
        
#         return JSONResponse(
#             status_code=401,
#             content={
#                 "status": "error",
#                 "message": "Invalid Authentication Token",
#                 "details": str(e)
#             }
#         )