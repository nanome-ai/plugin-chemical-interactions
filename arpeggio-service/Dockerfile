FROM harryjubb/arpeggio

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt
CMD gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app --timeout 120
