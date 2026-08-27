FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# build-essential + libminiupnpc-dev: miniupnpc has a C extension that needs
# a build toolchain and the miniupnpc headers to compile against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libminiupnpc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY adapter.py upnp.py .

CMD ["python3", "adapter.py"]
