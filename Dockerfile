# Use a lightweight Python version
FROM python:3.11-slim

# Set the working directory inside the server
WORKDIR /app

# Copy the requirements file and install libraries
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your code into the server
COPY . .

# Create the data directory (where the DB will live)
RUN mkdir -p data

# Run the bot
CMD ["python", "-m", "src.main"]