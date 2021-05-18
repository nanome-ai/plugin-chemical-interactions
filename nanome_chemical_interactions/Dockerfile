FROM nanome/plugin-env

WORKDIR /app

ENV ARGS=''
ARG CACHEBUST

COPY . /app
COPY ../requirements.txt .
RUN pip install -r requirements.txt

CMD python ChemicalInteractions.py $ARGS -a $NTS_HOST -p $NTS_PORT -r -v
