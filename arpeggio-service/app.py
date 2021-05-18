import os
import shutil
import tempfile

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/', methods=['POST'])
def index():
    input_file = request.files['input_file']

    temp_dir = tempfile.mkdtemp()
    temp_filepath = '{}/{}'.format(temp_dir, input_file.filename)
    input_file.save(temp_filepath)

    # Set up and runarpeggio command
    output_dir = ''
    flags = '-s RESNAME:FMM -v'
    output_flag = '-op {}'.format(output_dir) if output_dir else ''
    command = 'python /arpeggio/arpeggio.py {} {} {}'.format(
        temp_filepath, flags, output_flag)
    os.system(command)

    # Zip output files, and send back to client
    file_list = os.listdir(temp_dir)
    file_list.remove(input_file.filename)
    zipfile = shutil.make_archive('/tmp/{}'.format(input_file.filename), 'zip', temp_dir)
    return send_file(zipfile)


app.run(host='0.0.0.0', port=8000)
