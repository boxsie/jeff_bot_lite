FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
            ffmpeg

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

COPY ./ /app/

ENTRYPOINT ["python", "-u", "/app/run.py"]