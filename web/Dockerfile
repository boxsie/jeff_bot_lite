FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
            nodejs \
            npm

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

COPY ./ /app/

RUN npm install && npm run build

ENTRYPOINT ["python", "-u", "/app/run.py"]