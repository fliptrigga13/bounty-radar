FROM python:3.11-slim

# Create non-root user
RUN useradd --create-home --shell /usr/sbin/nologin radar
WORKDIR /app

# Copy application source and assets
COPY db.py radar.py a2a_server.py enrich.py test_a2a_server.py test_radar.py ./
COPY .well-known ./.well-known
COPY AGENT_INTEGRATION.md README.md .env.example ./

# Configure persistent data directory
ENV RADAR_DB=/data/radar.db
RUN mkdir -p /data && chown -R radar:radar /app /data
VOLUME ["/data"]

# Healthcheck hits /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4); sys.exit(0 if r.status==200 else 1)"

USER radar

EXPOSE 8080
CMD ["python", "a2a_server.py"]
