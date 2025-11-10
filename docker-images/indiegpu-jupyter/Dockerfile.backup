# docker-images/indiegpu-jupyter/Dockerfile
FROM jupyter/datascience-notebook:latest

# Switch to root for system packages
USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git-lfs \
    htop \
    nvtop \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Switch back to jovyan user
USER jovyan

# Install PyTorch with CUDA support
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install TensorFlow with GPU support (separate step to avoid conflicts)
RUN pip install --no-cache-dir \
    tensorflow[and-cuda]

# Install Hugging Face ecosystem
RUN pip install --no-cache-dir \
    transformers \
    datasets \
    accelerate \
    huggingface_hub

# Install experiment tracking and utilities
RUN pip install --no-cache-dir \
    wandb \
    tensorboard \
    gdown

# Install computer vision and data science packages
RUN pip install --no-cache-dir \
    opencv-python \
    scikit-learn \
    matplotlib \
    seaborn \
    plotly \
    pandas \
    numpy

# Configure git lfs
RUN git lfs install

# Create a comprehensive welcome notebook
COPY welcome.ipynb /home/jovyan/work/

# Set working directory
WORKDIR /home/jovyan/work
