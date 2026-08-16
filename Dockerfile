# A small, versioned base keeps local and EKS executions reproducible.
FROM python:3.12-slim

# Runtime metadata is informative and does not contain credentials.
LABEL org.opencontainers.image.title="PSI5120 Cloud Autoscaling API" \
      org.opencontainers.image.version="1.0.0-ta1"

# A fixed numeric UID/GID lets Kubernetes verify the non-root security policy.
RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app app
WORKDIR /app

# Install only pinned runtime dependencies and avoid retaining pip's cache.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application after dependencies to improve rebuild performance.
COPY app ./app
USER app

# The Kubernetes Service targets this documented application port.
EXPOSE 8080

# One worker per pod makes CPU requests and HPA observations easier to interpret.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
