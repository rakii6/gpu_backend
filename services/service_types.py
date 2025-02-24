# from typing import TYPE_CHECKING, Optional

# if TYPE_CHECKING:
#     from .docker_service import DockerService
#     from .session_manager import SessionManager
#     from .firebase_service import FirebaseService
#     from .redis import RedisManager

# services/service_types.py
from typing import TYPE_CHECKING, Optional, Protocol

# Define type stubs for our services
class SessionManager(Protocol):
    def __init__(self, redis_manager, firebase_service, gpu_manager, docker_service=None): ...

class DockerService(Protocol):
    def __init__(self, gpu_manager, firebase_service, redis_manager, session_manager=None): ...