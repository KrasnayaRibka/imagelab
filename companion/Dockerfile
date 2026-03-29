# Dockerfile for Uppy Companion server
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies
RUN npm install --only=production

# Copy companion configuration
COPY companion.js ./

# Expose Companion port
EXPOSE 3020

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3020/', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start Companion server
CMD ["node", "companion.js"]
