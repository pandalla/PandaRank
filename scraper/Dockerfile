FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies first
RUN pip install playwright==1.41.0

# Install browsers before changing user
RUN playwright install chromium && \
    playwright install-deps chromium

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 scraper && \
    chown -R scraper:scraper /app

# Copy browsers to scraper user's home directory
RUN mkdir -p /home/scraper/.cache && \
    cp -r /root/.cache/ms-playwright /home/scraper/.cache/ && \
    chown -R scraper:scraper /home/scraper/.cache/

USER scraper

# Expose metrics port
EXPOSE 8080

CMD ["python", "-m", "app.csv_main"]