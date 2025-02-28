FROM python:3.12.7-slim-bookworm

RUN curl -sSL https://install.python-poetry.org | python3 -
COPY pyproject.toml poetry.lock /overseer
WORKDIR /overseer
RUN poetry install --no-ansi --no-interaction

COPY app /overseer/app

COPY alembic.ini /overseer/alembic.ini
COPY alembic /overseer/alembic

ENTRYPOINT ["bash"]
CMD ["/app/entrypoint.sh"]
