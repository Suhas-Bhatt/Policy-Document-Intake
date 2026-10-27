FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-snowflake.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-snowflake.txt

COPY app/ app/
COPY run.py .

EXPOSE 5000

# $PORT is injected by platforms like Render; defaults to 5000 for `docker run` locally.
CMD gunicorn -b 0.0.0.0:${PORT:-5000} -w 2 run:app
