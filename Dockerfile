FROM python:3.12-slim
WORKDIR /app
COPY shortener /app/shortener
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV SHORTENER_DB=/data/shortener.db
# Development server intentionally binds loopback. For hosted use supply a
# production WSGI server/reverse proxy and auth/secrets per docs/SECURITY.md.
CMD ["python", "-m", "shortener.api"]
