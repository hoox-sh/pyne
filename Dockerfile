# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependency files to the container
COPY backend/requirements.txt ./
COPY pyproject.toml ./
COPY README.md ./
COPY LICENSE ./

# Install dependencies
# We install pynescript in editable mode or strict mode depending on need.
# Since we are in the repo, we can install the current directory.
# First, install backend requirements (Flask, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY src ./src
COPY backend ./backend

# Install the pynescript package from source
RUN pip install --no-cache-dir .

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application
# We run the app module directly
CMD ["python", "-m", "backend.app"]
