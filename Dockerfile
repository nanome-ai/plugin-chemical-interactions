FROM nanome/plugin-env

ARG work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

# Build arpeggio environment.
COPY environment.yml $work_dir/environment.yml
RUN conda env update -f environment.yml

# Install fork of Arpeggio until PDB issue gets resolved
# https://github.com/PDBeurope/arpeggio/issues/4
# ARG arpeggio_path=/opt/conda/envs/arpeggio/lib/python3.7/site-packages/arpeggio
# RUN git clone https://github.com/mjrosengrant/arpeggio /tmp/arpeggio_fork
# RUN rm -rf ${arpeggio_path}
# RUN cp -r /tmp/arpeggio_fork/arpeggio ${arpeggio_path}

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . $work_dir

CMD python chem_interactions/run.py {ARGS}
