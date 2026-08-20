###########
# BUILDER #
###########
FROM python:3.13-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build dependencies (if any wheels need compiling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    python3-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set up virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install packages
RUN python3 -m pip install --upgrade pip
COPY ./requirements.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    python3 -m pip install --no-cache-dir -r /requirements.txt


#########
# FINAL #
#########
FROM python:3.13-slim

# Runtime deps for Docling (OpenMP, OpenCV/libGL for table/OCR models)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# transformers>=5's rt_detr_v2 layout model (docling-layout-heron) tries to JIT-compile
# via torch.compile/Inductor, which needs a C++ compiler this minimal runtime stage
# doesn't have (only the builder stage does). Disabling dynamo avoids pulling in a full
# compiler toolchain just for this; it's also faster (no JIT warm-up per conversion).
ENV TORCHDYNAMO_DISABLE=1

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# OpenCV's cv2/typing can shadow stdlib typing in uvicorn --reload spawn workers.
# Preload stdlib typing on every interpreter start (see opencv/opencv#28766).
RUN python -c "import site; open(site.getsitepackages()[0] + '/sitecustomize.py', 'w').write('import typing\n')"

# Switch to non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Pre-download Docling models at build time so first parse is not slow
RUN python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"

# Copy application code as non-root
WORKDIR /app
COPY --chown=appuser:appuser app/ /app/app
ENV PYTHONPATH=/app

# Opened ports
EXPOSE 80

CMD ["uvicorn", "app.dash_app:server", "--host", "0.0.0.0", "--port", "80", "--timeout-keep-alive", "300", "--ws-ping-timeout", "300" ]
