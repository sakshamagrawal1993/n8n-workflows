FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn yfinance

# Copy the server script
COPY yfinance_server.py .

# Expose the port
EXPOSE 8001

# Run the server
CMD ["uvicorn", "yfinance_server:app", "--host", "0.0.0.0", "--port", "8001"]
