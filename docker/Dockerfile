FROM nanome/plugin-env

ENV ARGS=''

ARG CACHEBUST

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

CMD python run.py $ARGS -a $NTS_HOST -p $NTS_PORT -r -v
