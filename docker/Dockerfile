FROM nanome/plugin-env

ENV ARGS=''

# TODO: install dependencies here

ARG CACHEBUST

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt

CMD python run.py ${ARGS}
