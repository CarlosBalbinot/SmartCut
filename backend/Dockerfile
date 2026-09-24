FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Item 5.2: schema governado por migrações Alembic versionadas — aplica
# `alembic upgrade head` no boot (banco Postgres do compose) antes do uvicorn.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
