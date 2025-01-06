module.exports = {
    apps: [{
      name: "fastapi-app",
      script: "uvicorn",
      args: "main:app --host 0.0.0.0 --port 8080",
      interpreter: "python3",
      watch: true,
      cwd: "/home/rakii06/Docker-python"
    }]
  }