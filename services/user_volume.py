import os
import json
import shutil

class UserVolumeManager:
    def __init__(self, config):
        self.base_path = config["storage_path"]
        self.template_path = config["templates_path"]
        
    async def create_user_volumes(self, user_id):
        """Create the directory structure and mounted volumes for a user"""
        user_path = f"{self.base_path}/{user_id}"
        
        # Create main directories
        directories = [
            "notebooks",
            "data",
            "models",
            "config",
            "logs",
            "temp"
        ]
        
        # Create each directory with proper permissions
        for directory in directories:
            full_path = f"{user_path}/{directory}"
            os.makedirs(full_path, exist_ok=True)
            # Set permissions - only this user can access
            os.chmod(full_path, 0o700)
            
        # Copy template files
        self._copy_templates(user_id)
        
        # Create volume config for container mounting
        volume_config = {
            "user_root": user_path,
            "volumes": {
                f"{user_path}/notebooks": {"bind": "/home/jovyan/work", "mode": "rw"},
                f"{user_path}/data": {"bind": "/home/jovyan/data", "mode": "rw"},
                f"{user_path}/models": {"bind": "/home/jovyan/models", "mode": "rw"},
                f"{user_path}/config": {"bind": "/home/jovyan/config", "mode": "ro"},
                f"{user_path}/logs": {"bind": "/home/jovyan/logs", "mode": "rw"},
            }
        }
        
        # Store the volume config for this user
        with open(f"{user_path}/config/volumes.json", "w") as f:
            json.dump(volume_config, f, indent=2)
            
        return volume_config
    
    def _copy_templates(self, user_id):
        """Copy starter notebooks and config templates"""
        user_path = f"{self.base_path}/{user_id}"
        
        templates = {
            "notebooks": ["welcome.ipynb", "pytorch_intro.ipynb", "tensorflow_intro.ipynb"],
            "config": ["jupyter_config.py", "env_setup.sh"]
        }
        
        for directory, files in templates.items():
            for file in files:
                src = f"{self.template_path}/{directory}/{file}"
                dst = f"{user_path}/{directory}/{file}"
                if os.path.exists(src):
                    shutil.copy2(src, dst)