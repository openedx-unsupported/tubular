FROM python:3.8.6-buster

WORKDIR /app
ADD . /app
RUN pip install --upgrade pip
RUN pip install .
