# from fastapi import APIRouter, Depends, HTTPException, Request, 
Ans ~ APIRouter, lets you group related routes (like all your auth stuff) under a prefix (e.g., /auth). Think of it as a mini-app inside your main FastAPI app.

~Depends: A cool FastAPI trick to inject things (like a logged-in user check) into your routes automatically. Idk why I am using this, but I took some inspiration I guess.

~ HTTPException: For throwing errors like wrong pass etc with codes like 401 or 400

~ Request and Response: These give us raw access to incoming requests and outgoing responses if we need to make some changes, these are the guys.

# from pydantic import BaseModel, EmailStr, Field

~BaseModel: The foundation for creating structured data models (like signup form). It validates data automatically—super handy!

~EmailStr: A special type that ensures a field is a valid email (e.g., user@example.com).

~Field: Lets you add rules to fields, like “password must be at least 6 characters.”

# import firebase_admin & from firebase_admin import auth
~Firebase is Google’s backend service. The firebase_admin library connects my app to Firebase, and auth specifically handles user authentication (creating users, verifying logins, etc.).

# from typing import Optional
~ This lets us mark fields optional in the models( like name might not always be there)

# router = APIRouter(prefix = "/auth", tags=["Authentication"])
~This is cuz we are creating a router with  /auth prefix, all the auth routes or pages will start with /auth. The "tags" part groups all these auth routes under "Authentication" grroup in FastApi's generated docs(/docs).

# Request & Response Models or Class you can say........

~Thesee are actually blueprints or schema you can say, that is expected how the data will be structured and sent or recieved with the client and system. We are using
Pydantics Basemodel to enfore the strcuter and Validation, remember BaseModel of pydantice ....striclty to enforce validation and structre

for example in the class SigupRequest(BaseModel):
                    email:EmailStr,
                    password:str = Field(......, min_length=6)
                    name :str
so Pydantic's Basemodel checks wether the request that is being sent is in this above strcuture or not. If not it gives errror

# Class TokenResponse(BaseModel)
~ okay here it is what you send back after a successfull login or signup by the system to the front end. Remember only after a successfull sign up or login this Token is sent in the given structre

# Fields in the TokenResponse:
~ access_token: str: A key (JWT from Firebase, probably) the user uses to prove they’re logged in. Its generated in the server side.

~token_type: str = "bearer": Tells the client how to use the token (standard is “bearer” for JWTs).

~user_id: str: The user’s unique ID from Firebase.

~name: Optional[str] = None and email: Optional[str] = None: Optional fields (can be None) for extra user info.

Why did we create this Token and the structure, why did we do this ???
~This is the “you’re in!” package—gives the client what they need to keep the user authenticated. So in frontend when they  call a auth route and get this Token, the front end system will know "Hey so we got the token, now we allow this user to proceed"

Now lets proceed with the other parts of code,

# @router.post('/signup', response_model=TokenResponse) & async def signup(request: SignUpRequest):
~Here the aim is creating a user in the /auth/signup route, and underneath a fucntion defiend, with a param called request. We did this so that the function can access the parts of http request being sent from the front end like this 
fetch("http://your-api/auth/signup", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "john@example.com", password: "secret123", name: "John" })
});

so in the server side, the Fastapi gets the body  of the http request and checks it with the SignUpRequest schema or model or the class or whatever.

Now about reponse_model= TokenResponse, its an optional argument used in the @route decorator. So its says, “This route returns something that looks like TokenResponse.” So, clients expect JSON with access_token, token_type, user_id, etc.

Example output:
json

{
  "access_token": "some-token",
  "token_type": "bearer",
  "user_id": "firebase-uid-123",
  "name": "John",
  "email": "john@example.com"
}

Before sending the response, FastAPI checks it against TokenResponse. If you forget a required field (like access_token) or mess up the types, it raises an error before the client sees it.

Example: If you return { "user_id": "123" }  but missing access_token, FastAPI catches it and yells at you.
 We can have the option of not using this arg, and just return plain old dictonary, no validation,Docs are vague “object” instead of a detailed schema etc etc. So response_model is like a guard for your output—keeps it legit and tells everyone what’s coming.

 































