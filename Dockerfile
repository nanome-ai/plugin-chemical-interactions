FROM nanome/plugin-env

ARG work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

# Build arpeggio environment.
COPY environment.yml $work_dir/environment.yml
RUN conda env update -f environment.yml

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . $work_dir

CMD python chem_interactions/run.py {ARGS}
