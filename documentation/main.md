Main.py Documentation

main.py servers as the entry point and its core. Initializing all the services and setiing up Fast API application, middlewares and app.state

Core Components:~

redis_manager = RedisManager()
firebase_service = FirebaseService()
docker_service = None
gpu_manager = None
session_manager = None

They are globally declared variable to be used everywhere in the app, note that some are init as None initally, and re populated later on in the lifesapn context.


Lifespan Context Manager:~

@asynccontextmanager
async def lifespan(app: FastAPI): this here is the syntax given by the FASTapi docs, read the docs for its inner working. In Gist this feature of FastAPI is to handle the lifecycle of the app when it starts, taking care of variable or services that ought to be ready. 
The cycle repeats after an interval(refer to the FASTAPI docs for further needs.)

INITIALIZATION ORDER >

Gpu manager is initialized first using the redis manager >> Session Manager initialzed next using redis, firebase, gpu but without docker>> Docker service is initialzed using gpu_manger, redis & firebase but without session_manager

Circular Dependency Resolution:~

The code handles a circular dependency between DockerService and SessionManager:
    docker_service._session = session_manager
    session_manager._docker = docker_service
    
This is resolved by:

    1)Initially creating services with None for circular dependencies
    2)Cross-linking after both services are initialized
    3)Using property decorators to handle the relationship. 

App.state Section :~

app.state.redis = redis_manager
app.state.firebase = firebase_service
app.state.docker = docker_service
app.state.gpu = gpu_manager
app.state.session_service = session_manager

Why did I do this? ~ To store and create instances of the services, in a central place which is availed by all. Instead of crreating new instances for a new request, I created them all in the startup.

* class RateLimitMiddleware(BaseHTTPMiddleware) what is this ? 

Ans ~ so we created a class inheritnace that inherits from Starlette's BaseHTTPMiddleware. Gives us the basic middleware structure, allowing us to intercept requests. Then in the Initialization section, we give 2 params FastAPI app and the Rate limiter we created.

This code super().__init__(app) ~ Calls for parent class initialization, Starelette's thing above.

* async def dispatch(self, request, call_next) , what is This ??
Ans~ This is the main middleware logic. request: The incoming HTTP request && call_next: A function to pass the request to the next middleware/route


* blocked_paths = ['/docs', '/redoc', '/openapi.json', '/docs/oauth2-redirect']
if any(request.url.path.startswith(path) for path in blocked_paths) 
 
Ans~ its a straight forward logic, just block the given path starting with the above urls. Simple! 

* await self.rate_limiter.check_rate_limit(request), what is this ?
Ans~ this is rate limiter, if a certain path is not blocked, it keeps a check on the number of times a certain path is requested for. Security measures.

 * response = await call_next(request)
    return response , what are these

Ans ~ If all checks pass, calls the next middleware/route
Returns whatever response they generate.

* app = FastAPI(lifespan=lifespan)
  rate_limiter = RateLimiter(redis_manager), what are these ??

Ans~ Here I :
        >Create the main FastAPI application
        >Pass in the lifespan manager we created earlier.
        >Create a RateLimiter instance using Redis manager.

* app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter) , what is this ?
Ans ~This adds the rate limiting middleware to the application pipeline, so it runs on every request.

* app.add_middleware(CORSMiddleware, **CORS_CONFIG), what is this ?
Ans ~ This adds Cross-Origin Resource Sharing (CORS) middleware:

>Allows requests from specified origins (in your case, "*.indiegpu.com")
>Required for web browsers to make requests to your API
>Configuration comes from your settings.py

app.include_router(general.router)
app.include_router(docker.router)
general routers thats all
