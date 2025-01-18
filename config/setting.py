# app/config/settings.py

CORS_CONFIG = {
    "allow_origins": ["*.indiegpu.com"],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

DOCKER_CONFIG = {
    "jupyter_notebook": {
        "image": "jupyter/datascience-notebook",
        "ports": {'8888/tcp': 8888},
        "environment": [
            "JUPYTER_ENABLE_LAB=yes",
            "JUPYTER_TOKEN=mysecret123"
        ]
    },
    "pytorch": {
        "image": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        "ports": {'8888/tcp': 8891},
        "environment": [
            "JUPYTER_ENABLE_LAB=yes",
            "JUPYTER_TOKEN=mysecret123"
        ]
    }
}