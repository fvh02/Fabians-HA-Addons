# build123d (Python CAD on the OpenCASCADE kernel) comes as ready wheels for amd64 and arm64.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libexpat1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -c "import build123d; build123d.Box(1, 1, 1)"

COPY app /app
COPY run.sh /run.sh
RUN chmod a+rx /run.sh && chmod -R a+rX /app
CMD [ "/run.sh" ]
