# Use a Python slim base image for smaller size
FROM python:3.9-slim-bullseye
# Removed the comment: # Or bookworm

# Install system dependencies (tesseract-ocr, poppler-utils, and libgl1-mesa-glx)
# Ensure apt-get update is run before installs
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set the TESSERACT_CMD environment variable for pytesseract
ENV TESSERACT_CMD /usr/bin/tesseract

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port your FastAPI app will listen on (matches fly.toml)
EXPOSE 10000

# Command to run your FastAPI application using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]