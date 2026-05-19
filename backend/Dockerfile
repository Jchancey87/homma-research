# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for some python packages (like lxml, pillow)
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    zlib1g-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

# Create directory for database and storage if they don't exist
RUN mkdir -p ../data ../storage/charts

# Expose the port FastAPI runs on
EXPOSE 5000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application using uvicorn
CMD ["uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "5000"]
