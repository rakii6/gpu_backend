import os
import json
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from services.redis import RedisManager


class SimpleStorageManager:
    """
    Simplified StorageManager for IndieGPU
    Start here to understand the core concepts
    """
    
    def __init__(self, base_path: str, redis_manager: RedisManager):
        self.base_path = Path("/home/rakii06/user_data")  # e.g., "/home/rakii06/user_data"
        self.redis = redis_manager.redis
        
        # Simple storage limits (in bytes)
        self.quotas = {
            "free": 10 * 1024 * 1024 * 1024,    # 5GB
            "pro": 25 * 1024 * 1024 * 1024     # 25GB
        }
        
        # Dangerous file extensions we won't allow
        self.blocked_extensions = {
            '.exe', '.bat', '.sh', '.dll', '.sys', '.msi'
        }
        
        # Make sure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        print(f"Storage initialized at: {self.base_path}")

    async def create_user_folder(self, user_id: str, tier: str = "free") -> Dict:
        """
        Step 1: Create basic folder structure for new user
        This is called when user signs up
        """
        try:
            print(f"Creating storage for user: {user_id}")
            
            # Create user's main folder
            user_folder = self.base_path / user_id
            user_folder.mkdir(exist_ok=True) #.mkdir creates the folder
            
            # Create subfolders
            folders_to_create = [
                "workspace_default",  # Their first workspace
                "shared_data",         # For datasets they want to keep
                "uploads"              # Temporary upload area
            ]
            
            for folder in folders_to_create:
                (user_folder / folder).mkdir(exist_ok=True)
                print(f"Created: {user_folder / folder}")
            
            # Set folder permissions (only user can access)
            os.chmod(user_folder, 0o700)
            
            # Track user's quota in Redis
            redis_key = f"storage:{user_id}"
            self.redis.hset(redis_key, mapping={
                "tier": tier,
                "quota_bytes": str(self.quotas[tier]),
                "used_bytes": "0",
                "created_at": datetime.now().isoformat()
            })
            
            print(f"Storage tracking set up in Redis: {redis_key}")
            
            return {
                "status": "success",
                "message": f"Storage created for {user_id}",
                "user_path": str(user_folder),
                "quota_gb": self.quotas[tier] / (1024**3)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create user storage: {str(e)}"
            }

    async def check_file_is_safe(self, filename: str, file_content: bytes) -> Dict:
        """
        Step 2: Basic file security check
        This runs before we save any file
        """
        try:
            print(f"Checking file safety: {filename}")
            
            # Check 1: File extension
            file_ext = Path(filename).suffix.lower()
            if file_ext in self.blocked_extensions:
                return {
                    "status": "blocked",
                    "reason": f"File type {file_ext} is not allowed"
                }
            
            # Check 2: File size (max 100MB for now)
            max_size = 100 * 1024 * 1024  # 100MB
            if len(file_content) > max_size:
                return {
                    "status": "blocked", 
                    "reason": f"File too large: {len(file_content)/1024/1024:.1f}MB (max: 100MB)"
                }
            
            # Check 3: Look for dangerous content in first 1000 bytes
            dangerous_patterns = [
                b'#!/bin/bash',
                b'cmd.exe', 
                b'powershell',
                b'rm -rf',
                b'format c:'
            ]
            
            file_start = file_content[:1000].lower()
            for pattern in dangerous_patterns:
                if pattern in file_start:
                    return {
                        "status": "suspicious",
                        "reason": f"File contains potentially dangerous code"
                    }
            
            # File looks safe
            return {
                "status": "safe",
                "message": "File passed security checks"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Security check failed: {str(e)}"
            }

    async def check_user_quota(self, user_id: str, file_size: int) -> Dict:
        """
        Step 3: Check if user has enough space
        """
        try:
            # Get current usage from Redis
            redis_key = f"storage:{user_id}"
            user_data = self.redis.hgetall(redis_key)
            
            if not user_data:
                return {
                    "status": "error",
                    "message": "User storage not found - call create_user_folder first"
                }
            
            # Decode Redis data
            current_used = int(user_data[b'used_bytes'].decode())
            quota_limit = int(user_data[b'quota_bytes'].decode())
            tier = user_data[b'tier'].decode()
            
            # Check if adding this file would exceed quota
            new_total = current_used + file_size
            
            if new_total > quota_limit:
                return {
                    "status": "quota_exceeded",
                    "message": f"Not enough space. Used: {current_used/1024/1024:.1f}MB, Available: {(quota_limit-current_used)/1024/1024:.1f}MB",
                    "current_used_mb": current_used / 1024 / 1024,
                    "quota_limit_mb": quota_limit / 1024 / 1024
                }
            
            return {
                "status": "ok",
                "message": "Quota check passed",
                "space_after_upload_mb": (quota_limit - new_total) / 1024 / 1024
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Quota check failed: {str(e)}"
            }

    async def save_file(self, user_id: str, filename: str, file_content: bytes, workspace: str = "workspace_default") -> Dict:
        """
        Step 4: Actually save the file after all checks pass
        """
        try:
            print(f"Saving file {filename} for user {user_id}")
            
            # Step 4a: Run security check
            safety_check = await self.check_file_is_safe(filename, file_content)
            if safety_check["status"] != "safe":
                return safety_check
            
            # Step 4b: Check quota
            quota_check = await self.check_user_quota(user_id, len(file_content))
            if quota_check["status"] != "ok":
                return quota_check
            
            # Step 4c: Save the file
            user_folder = self.base_path / user_id
            workspace_folder = user_folder / workspace
            
            # Make sure workspace exists
            workspace_folder.mkdir(exist_ok=True)
            
            # Handle duplicate filenames
            file_path = workspace_folder / filename
            counter = 1
            original_name = Path(filename)
            
            while file_path.exists():
                new_name = f"{original_name.stem}_{counter}{original_name.suffix}"
                file_path = workspace_folder / new_name
                counter += 1
                print(f"File exists, trying: {new_name}")
            
            # Write the file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Remove execute permission for security
            os.chmod(file_path, 0o644)
            
            # Step 4d: Update quota usage in Redis
            redis_key = f"storage:{user_id}"
            self.redis.hincrby(redis_key, "used_bytes", len(file_content))
            
            print(f"File saved: {file_path}")
            
            return {
                "status": "success",
                "message": f"File {file_path.name} saved successfully",
                "file_path": str(file_path.relative_to(self.base_path)),
                "file_size_mb": len(file_content) / 1024 / 1024
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to save file: {str(e)}"
            }

    async def get_user_workspaces(self, user_id: str) -> Dict:
        """
        Step 5: List all workspaces user has
        This is for the "choose workspace" dropdown
        """
        try:
            user_folder = self.base_path / user_id
            
            if not user_folder.exists():
                return {
                    "status": "error",
                    "message": "User storage not found"
                }
            
            workspaces = []
            
            # Find all workspace folders
            for folder in user_folder.iterdir():
                if folder.is_dir() and folder.name.startswith('workspace_'):
                    # Calculate folder size
                    total_size = sum(f.stat().st_size for f in folder.rglob('*') if f.is_file())
                    file_count = sum(1 for f in folder.rglob('*') if f.is_file())
                    
                    workspaces.append({
                        "name": folder.name,
                        "size_mb": round(total_size / 1024 / 1024, 2),
                        "file_count": file_count,
                        "created": datetime.fromtimestamp(folder.stat().st_ctime).isoformat()
                    })
            
            return {
                "status": "success",
                "workspaces": workspaces,
                "total_workspaces": len(workspaces)
            }
            
        except Exception as e:
            return {
                "status": "error", 
                "message": f"Failed to list workspaces: {str(e)}"
            }

    async def get_docker_volumes(self, user_id: str, workspace_name: str) -> Dict:
        """
        Step 6: Generate Docker volume mounts for container
        This is what your DockerService will use
        """
        try:
            user_folder = self.base_path / user_id
            workspace_folder = user_folder / workspace_name
            
            if not workspace_folder.exists():
                return {
                    "status": "error",
                    "message": f"Workspace {workspace_name} not found"
                }
            
            # Docker volume configuration
            volumes = {
                str(workspace_folder): {"bind": "/workspace", "mode": "rw"},
                str(user_folder / "shared_data"): {"bind": "/shared", "mode": "rw"}
            }
            
            return {
                "status": "success",
                "volumes": volumes,
                "workspace_path": str(workspace_folder)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to generate volumes: {str(e)}"
            }

    async def get_storage_stats(self, user_id: str) -> Dict:
        """
        Step 7: Get user's storage usage info
        For dashboard display
        """
        try:
            # Get from Redis
            redis_key = f"storage:{user_id}"
            user_data = self.redis.hgetall(redis_key)
            
            if not user_data:
                return {"status": "error", "message": "User storage not found"}
            
            used_bytes = int(user_data[b'used_bytes'].decode())
            quota_bytes = int(user_data[b'quota_bytes'].decode())
            tier = user_data[b'tier'].decode()
            
            return {
                "status": "success",
                "user_id": user_id,
                "tier": tier,
                "used_mb": round(used_bytes / 1024 / 1024, 2),
                "quota_mb": round(quota_bytes / 1024 / 1024, 2),
                "available_mb": round((quota_bytes - used_bytes) / 1024 / 1024, 2),
                "usage_percent": round((used_bytes / quota_bytes) * 100, 1)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get storage stats: {str(e)}"
            }

# Example usage in your FastAPI routes:
"""
# In your main.py or wherever you initialize services
storage_manager = SimpleStorageManager("/home/rakii06/user_data", redis_manager)

# When user signs up:
await storage_manager.create_user_folder(user_id, "free")

# When user uploads file:
result = await storage_manager.save_file(user_id, filename, file_content)

# When creating container:
volumes = await storage_manager.get_docker_volumes(user_id, "workspace_default")
"""