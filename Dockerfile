FROM python:3.11-slim

# Run as non-root
RUN useradd --create-home --shell /usr/sbin/nologin radar
WORKDIR /app

COPY radar.py a2a_server.py enrich.py test_a2a_server.py ./
COPY .well-known ./well-known-staging/.well-known
COPY AGENT_INTEGRATION.md README.md .env.example ./

# healthcheck hits the A2A server's health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4); sys.exit(0 if r.status==200 else 1)"

ENV RADAR_DB=/data/radar.db
VOLUME ["/data"]
RUN mkdir -p /data && chown -R radar:radar /app /data
USER radar

EXPOSE 8080
CMD ["python", "a2a_server.py"]
