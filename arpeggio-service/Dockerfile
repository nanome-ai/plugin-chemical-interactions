FROM harryjubb/arpeggio

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt
CMD gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app
