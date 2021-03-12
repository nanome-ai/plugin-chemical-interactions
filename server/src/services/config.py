import requests

image='harryjubb/arpeggio:latest'
flags=r'-v "{{files}}":/run -u `id -u`:`id -g`'
command = 'python arpeggio.py /run/1XKK.pdb -s RESNAME:FMM -v'
with open('1XKK.pdb', 'r') as f:
	file = f.read()


res = requests.post('http://localhost:80/', data={'flags': flags, 'image': image, 'command': command}, files={'1XKK.pdb': file})