FROM nanome/plugin-env

ENV ARGS=''

ARG CACHEBUST

COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

CMD docker-compose up
