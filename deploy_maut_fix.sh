#!/bin/bash
# Deploy MAUT fix to production containers
set -e
echo "Committing containers..."
docker commit agentsim-prod-api agentsim-backend-core:prod
docker commit agentsim-prod-worker agentsim-backend-core:prod
docker commit agentsim-prod-monitor agentsim-backend-core:prod
echo "Restarting containers..."
docker restart agentsim-prod-api agentsim-prod-worker agentsim-prod-monitor
echo "Done. Checking health..."
sleep 3
curl -fsS http://127.0.0.1:8000/health && echo "API health OK"
