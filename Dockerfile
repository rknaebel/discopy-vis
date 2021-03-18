FROM python:3.7
MAINTAINER René Knaebel <rene.knaebel@uni-potsdam.de>

# set gpu as unavailable
ENV CUDA_VISIBLE_DEVICES=''

# copy the dependencies file to the working directory
COPY requirements.txt /requirements.txt
RUN pip install -U pip wheel setuptools
RUN pip install -r /requirements.txt

# set the working directory in the container
WORKDIR /app

# copy the content of the local src directory to the working directory
COPY app .

# command to run on container start
CMD python run.py --port 8000
