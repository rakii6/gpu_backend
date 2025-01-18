from fastapi import APIRouter
from services.docker_service import DockerService
from services.firebase_service import FirebaseService
from typing import Dict
from schemas.docker import ContainerRequest

router = APIRouter(prefix="/docker")
firebase_service = FirebaseService()
docker_service = DockerService(firebase_service)


@router.get('/check')
async def check_docker():
    return await docker_service.check_docker()
@router.post('/run')
async def run_container():
    return await docker_service.run_container()
@router.get('/user/{user_id}/containers')
async def get_user_containers(user_id: str):
    return await firebase_service.get_user_container(user_id)
@router.post('/environment/create')
async def creation_of_environment(request: ContainerRequest):
    return await docker_service.create_user_environment(request)
#Test endpoints:

# @router.post('/test/jupyter')
# async def test_jupyter_container():
#     try:
#         container_data = await docker_service.create_user_environment(

#         )

@router.post('/test/create-user')
async def create_test_user():
    """Create a test user and return their ID"""
    return await firebase_service.create_test_user()
