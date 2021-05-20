FROM nanome/plugin-env

ARG  work_dir=/app
WORKDIR $work_dir

ENV ARGS=''
ARG CACHEBUST

COPY . $work_dir
COPY ./requirements.txt .
RUN pip install -r requirements.txt

CMD python ChemicalInteractions.py $ARGS -a $NTS_HOST -p $NTS_PORT -r -v
