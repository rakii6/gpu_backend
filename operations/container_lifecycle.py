from ..services.docker_service import DockerService


class ContainerLifeCycle:

    def __init__(self):
        
        self.docker = DockerService(firebase_service=None)

async def stop_container(self, container_id:str, user_id:str):
    """stop the  Container Status"""

    container = self.docker.client.containers.get(container_id)
    container.stop(timeout=20)
    container_info = await firebase
    