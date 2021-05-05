FROM nanome/plugin-env

ENV ARGS=''

ARG CACHEBUST

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

CMD python run.py $ARGS -a $HOST -p $PORT -r -v
