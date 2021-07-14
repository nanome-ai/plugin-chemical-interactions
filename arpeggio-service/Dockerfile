FROM continuumio/miniconda3

WORKDIR /app
COPY . /app

RUN conda install python=3.7.10
RUN conda install -c openbabel openbabel
RUN pip install -r requirements.txt

# Install fork of Arpeggio until PDB issue gets resolved
# https://github.com/PDBeurope/arpeggio/issues/4
RUN git clone https://github.com/mjrosengrant/arpeggio ./arpeggio-fork
RUN ln -s arpeggio-fork /opt/conda/lib/python3.7/site-packages/arpeggio 

CMD gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app --timeout 60
