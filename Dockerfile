FROM nanome/plugin-env

ARG work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

COPY docker ${work_dir}/docker
RUN ./docker/build.sh

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . $work_dir

CMD python chem_interactions/run.py {ARGS}
