FROM python:3.12-slim

# Set environment variables to reduce image size
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Add container metadata
LABEL org.opencontainers.image.description="Docker image for Unshackle with all required dependencies for downloading media content"

# Install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    git \
    curl \
    build-essential \
    cmake \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up repos for mkvtools and bullseye for ccextractor
RUN wget -O /etc/apt/keyrings/gpg-pub-moritzbunkus.gpg https://mkvtoolnix.download/gpg-pub-moritzbunkus.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/gpg-pub-moritzbunkus.gpg] https://mkvtoolnix.download/debian/ bookworm main" >> /etc/apt/sources.list \
    && echo "deb-src [signed-by=/etc/apt/keyrings/gpg-pub-moritzbunkus.gpg] https://mkvtoolnix.download/debian/ bookworm main" >> /etc/apt/sources.list \
    && echo "deb http://ftp.debian.org/debian bullseye main" >> /etc/apt/sources.list

# Install all dependencies from apt
RUN apt-get update && apt-get install -y \
    ffmpeg \
    ccextractor \
    mkvtoolnix \
    aria2 \
    libmediainfo-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install shaka packager
RUN wget https://github.com/shaka-project/shaka-packager/releases/download/v2.6.1/packager-linux-x64 \
    && chmod +x packager-linux-x64 \
    && mv packager-linux-x64 /usr/local/bin/packager

# Install N_m3u8DL-RE
RUN wget https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.3.0-beta/N_m3u8DL-RE_v0.3.0-beta_linux-x64_20241203.tar.gz \
    && tar -xzf N_m3u8DL-RE_v0.3.0-beta_linux-x64_20241203.tar.gz \
    && mv N_m3u8DL-RE /usr/local/bin/ \
    && chmod +x /usr/local/bin/N_m3u8DL-RE \
    && rm N_m3u8DL-RE_v0.3.0-beta_linux-x64_20241203.tar.gz

# Create binaries directory and add symlinks for all required executables
RUN mkdir -p /app/binaries && \
    ln -sf /usr/bin/ffprobe /app/binaries/ffprobe && \
    ln -sf /usr/bin/ffmpeg /app/binaries/ffmpeg && \
    ln -sf /usr/bin/mkvmerge /app/binaries/mkvmerge && \
    ln -sf /usr/local/bin/N_m3u8DL-RE /app/binaries/N_m3u8DL-RE && \
    ln -sf /usr/local/bin/packager /app/binaries/packager && \
    ln -sf /usr/local/bin/packager /usr/local/bin/shaka-packager && \
    ln -sf /usr/local/bin/packager /usr/local/bin/packager-linux-x64

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Copy source code first
COPY unshackle/ ./unshackle/

# Install dependencies with uv (including the project itself)
RUN uv sync --frozen --no-dev

# Set entrypoint to allow passing commands directly to unshackle
ENTRYPOINT ["uv", "run", "unshackle"]
CMD ["-h"]
