FROM python:3.5-buster

WORKDIR /app
ADD . /app

RUN pip install .
