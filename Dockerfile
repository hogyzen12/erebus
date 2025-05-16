# Build stage
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && rustc --version

# Install Solana CLI
RUN sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)" \
    && /root/.local/share/solana/install/active_release/bin/solana --version

# Runtime stage
FROM --platform=linux/amd64 ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Copy Solana CLI binaries from builder stage
COPY --from=builder /root/.local/share/solana /root/.local/share/solana

# Configure Solana CLI with RPC URL
ARG SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
RUN solana config set --url ${SOLANA_RPC_URL}

# Set working directory
WORKDIR /app

# Copy project files
COPY bot.py .
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create directories for persistent storage
RUN mkdir -p /app/keypairs /app/bot_keypair

# Set permissions for keypairs directory
RUN chmod 700 /app/keypairs

# Command to run the bot
CMD ["python3", "bot.py"]