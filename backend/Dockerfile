# Use a pinned Python version (project targets 3.11+; avoids incompatible "latest"/new majors)
FROM --platform=linux/amd64 python:3.13-slim

# Set the working directory
WORKDIR /usr/backend

# Set up Python behaviour
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Tell Poetry to install into the system Python (no virtualenv needed inside Docker)
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_NO_INTERACTION=1

# Set the server port
EXPOSE 8000

# Install system dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      netcat-openbsd gcc postgresql-client curl \
  && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip && pip install poetry

# Copy only dependency files first (improves Docker layer caching)
COPY pyproject.toml poetry.lock ./

# Install only production dependencies
RUN poetry install --only main

# Copy all files
COPY . .

# Copy entrypoint.sh for auto connection with account_db service
COPY ./entrypoint.sh .
RUN chmod +x /usr/backend/entrypoint.sh

# Execute entrypoint.sh
ENTRYPOINT ["/usr/backend/entrypoint.sh"]

# Start up the backend server
# - `--reload-dir` ensures reload watches your source folder
# - installing `watchfiles` makes reload reliable on Docker Desktop bind mounts
CMD uvicorn src.main:backend_app --reload --reload-dir /usr/backend/src --host 0.0.0.0 --port 8000
