SO What’s Happening? The Big Picture->

This is an authentication middleware its like a checker or a bouncer that checks every incoming request to our app.
 # Remember 
 # request: Request,gives you the full HTTP request (URL, headers, cookies, etc.).

 # call_next is the function that passes the request to your actual route (e.g., signup or cleanup_container).
...................................................................................................................


# public_paths = ['/auth/login','/auth/signup', '/auth/reset-password', '/docs', '/openapi.json']
   # if any (request.url.path.startswith(path) for path in public_paths): 
   #    return await call_next(request) 
Explanation : Here the 3 lines are written to define public routes and private routes, so when a request is sent by the client into our app, the auth_middelware first checks that if the incoming request.url.path starts with any of the mentioned string above, 

If True, Skips all token checks and jumps straight to the route request via call_next(request).

If False: Moves to the token-checking steps.

...................................................................................................................

# token = request.cookies.get('access_token')
   # if not token:
   #     auth_header = request.headers.get('Authorization')
   #     if auth_header and auth_header.startswith('Bearer '):
   #         token = auth_header.replace('Bearer ', '')
 Explanation: Here the logic to check for token comes into the picture, so request.cookies.get() grabs the token from the cookies. If they app did not find it in the cookie, then request.headers.get looks for in the Authorizatin header. 

 If Authorization header exists & starts with "Bearer", it extarcts the  token
 If still no token then
    return JSONResponse(
        status_code=401,
        content={"status": "Error", "message": "Authentication Required"}
    )
    What’s Read: token (either from cookie, header, or still None).
    Its like saying, "get out"

...................................................................................................................

# try:

   #     user = auth.get_user(token)
   #     request.state.user = user
   #     request.state.user_id = user.uid

   #     return await call_next(request)

Explanation ~ So we get the token, (Bdw this is exhausting, writing docs for my future self to not get confused.Lol) then we try to get verification from the Firebase admin if the token is legit. And get the user object, it contains stuff like uid, email, etc.

Now request.state.user = user, this attaches the full user object to the request’s state (a bag for passing data to the route). And we add the user uid too with it. Once things are verified we proceed to call_next()


    





