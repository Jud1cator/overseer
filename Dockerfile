FROM python:3.12.7-slim-bookworm

ENV POETRY_VERSION=2.0.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local'

RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
    curl \
    && curl -sSL https://install.python-poetry.org | python3 

COPY pyproject.toml poetry.lock /overseer/
WORKDIR /overseer
RUN poetry install --no-ansi --no-interaction

COPY app /overseer/app

COPY alembic.ini /overseer/alembic.ini
COPY alembic /overseer/alembic

ENTRYPOINT ["bash"]
CMD ["/overseer/app/entrypoint.sh"]
