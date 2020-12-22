FROM python:3.6-buster

WORKDIR /app
ADD . /app

RUN pip install .
