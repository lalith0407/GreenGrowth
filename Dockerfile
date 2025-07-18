# Step 1: Use an official Python runtime as a parent image
FROM python:3.11-slim

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Install system dependencies required for your application
# This is where we install Tesseract for OCR
RUN apt-get update && apt-get install -y tesseract-ocr --no-install-recommends

# Step 4: Copy the Python requirements file into the container
COPY requirements.txt .

# Step 5: Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 6: Copy the rest of your application's code into the container
# This includes main.py, silent.py, pdffilling.py, and fillable-1040.pdf
COPY . .

# Step 7: Expose the port your app will run on
EXPOSE 10000

# Step 8: Define the command to run your application
# This is what Render will execute when the container starts
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
