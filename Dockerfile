# Use the official Playwright image pinned to the same Playwright version as the app.
FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# The Playwright image already has a user with UID 1000, so we use it directly
# Set environment for non-root user
ENV HOME=/home/pwuser \
	PATH=/home/pwuser/.local/bin:$PATH

# Set the working directory
WORKDIR /home/pwuser/app

# Copy the current directory contents into the container
COPY --chown=pwuser:pwuser . /home/pwuser/app

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m py_compile app.py

# Streamlit runs on 8501 by default, but HF Spaces expects 7860
EXPOSE 7860

# Run the application
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=7860"]
