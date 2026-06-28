FROM python:3.13-slim

WORKDIR /app

# Install Python dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and data.
COPY . .

EXPOSE 8501

# The Ollama server runs in its own container (see docker-compose.yml).
# This default is overridden by docker-compose with the ollama service name.
ENV OLLAMA_HOST=http://ollama:11434

CMD ["streamlit", "run", "energy_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
