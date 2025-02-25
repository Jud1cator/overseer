FROM python:3.12.7-slim-bookworm

RUN curl -sSL https://install.python-poetry.org | python3 -
WORKDIR /overseer
COPY pyproject.toml poetry.lock /overseer
RUN poetry install --no-ansi --no-interaction

COPY app /app

COPY alembic.ini alembic.ini
COPY alembic alembic

ENTRYPOINT ["bash"]
CMD ["/app/entrypoint.sh"]
