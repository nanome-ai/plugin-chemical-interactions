FROM continuumio/miniconda3

RUN conda install python=3.7.10
RUN conda install -c openbabel openbabel

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Install fork of Arpeggio until PDB issue gets resolved
# https://github.com/PDBeurope/arpeggio/issues/4
ARG arpeggio_path=/opt/conda/lib/python3.7/site-packages/arpeggio
RUN git clone https://github.com/mjrosengrant/arpeggio /tmp/
RUN rm -rf ${arpeggio_path}
RUN cp -r /tmp/arpeggio ${arpeggio_path}

CMD gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app --timeout 60
