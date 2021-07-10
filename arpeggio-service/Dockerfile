FROM continuumio/miniconda3

WORKDIR /app
COPY . /app

RUN conda install python=3.7.10
RUN conda install -c openbabel openbabel
RUN pip install -r requirements.txt

CMD gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app --timeout 60
