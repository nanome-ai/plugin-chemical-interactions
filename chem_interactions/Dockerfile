FROM nanome/plugin-env

ARG work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . $work_dir

CMD python run.py {ARGS}
