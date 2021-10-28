FROM nanome/plugin-env

ARG work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

# Build arpeggio environment.
COPY arpeggio_environ.yml $work_dir/arpeggio_environ.yml
RUN conda env update -f arpeggio_environ.yml

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . $work_dir

CMD python run.py ${ARGS}
