# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all other application files into the container at /app
COPY . .

# Ensure the bot token is set as an environment variable when running the container
# Define the command to run the bot
CMD ["python", "./bot.py"]
