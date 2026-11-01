FROM python:3.14-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

# Set working dir
WORKDIR /app
# Add env
ENV PATH="/app/.venv/bin:$PATH"

# Move uv files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy project to the image
COPY  . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

CMD [ "pytest" ]