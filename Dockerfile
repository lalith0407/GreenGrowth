# [cite_start]Use a Python slim base image for smaller size [cite: 1]
FROM python:3.9-slim-buster

# [cite_start]Install system dependencies (tesseract-ocr and poppler-utils for pdf2image) [cite: 1]
# Ensure apt-get update is run before installs
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# [cite_start]Set the TESSERACT_CMD environment variable for pytesseract [cite: 1]
ENV TESSERACT_CMD /usr/bin/tesseract

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code, including f1040.pdf
COPY . .

# Expose the port your FastAPI app will listen on (matches fly.toml)
EXPOSE 10000

# Command to run your FastAPI application using uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]