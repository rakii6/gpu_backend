module.exports = {
    apps: [{
      name: "fastapi-app",
      script: "uvicorn",
      args: "main:app --host 0.0.0.0 --port 8080",
      interpreter: "python3",
      watch: true,
      cwd: "/home/rakii06/Docker-python/env/bin/python3",
      max_restarts: 10,
      restart_delay: 3000
    },
    {
      name: "traefik",
      script:"docker-compose",
      args:"up trafik",
      cwd: "/home/rakii06/Docker-python",
      max_restarts:5,
      restart_delay:5000
    },
    {
      name: "cloudflare-tunnel",
      script: "cloudflared",
      args: "tunnel run",
      max_restarts: 5,
      restart_delay: 3000
    }
  
  
  ]
  }