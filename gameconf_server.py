#!/usr/bin/python3

# 
# HTTP server that serves gameconf requests from SourceMod installations.
# 

import http.server
import urllib.parse
import vdf
import itertools
import os
import shutil
import hashlib
import cgi

import configparser
config = configparser.ConfigParser()

def get_md5sum_str(file_path):
	# TODO cache this
	try:
		hasher = hashlib.md5()
		with open(file_path, 'rb') as f:
			for chunk in iter(lambda: f.read(4096), b''):
				hasher.update(chunk)
			return hasher.hexdigest()
	except (PermissionError) as e:
		pass
	return ''

"""
Returns generator of gameconf file paths relative to given directory.
"""
def gameconf_files(root_dir):
	if not root_dir:
		return
	
	# TODO cache this
	for subdir, dirs, files in os.walk(root_dir):
		# dirty hack to return either plain filename or subdirectory within root
		yield from ((root_dir, os.path.join(os.path.relpath(subdir, root_dir), f) if subdir != root_dir else f) for f in files)

"""
Returns a gameconf dir string based on version (e.g., "1.10")
"""
def detect_sm_gameconf_dir(sm_version):
	# TODO move this into an external configuration?
	sm_dir = '.'.join(map(str, sm_version[:2]))
	return sm_dir if os.path.exists(sm_dir) else None

"""
Given a dict {file_name=file_md5, ...}, yield tuples (str, {md5sum=, location=}) containing
destination filename and md5 / URL path.

Note that the submitted_files include the 'gamedata/' prefix, but the returned struct does not.
"""
def get_changed_gameconf(sm_version, submitted_files):
	# strip gamedata prefix from POST data
	remote_files = { os.path.relpath(f, 'gamedata'): s for f, s in submitted_files.items() }
	
	gameconf_dirs = [ detect_sm_gameconf_dir(sm_version), 'thirdparty' ]
	
	for r, f in itertools.chain.from_iterable(gameconf_files(f) for f in gameconf_dirs):
		remote_hash = remote_files.get(f)
		if not remote_hash:
			continue
		
		local_path = os.path.join(r, f)
		local_hash = get_md5sum_str(local_path)
		if remote_hash == local_hash:
			continue
		
		yield (f, { 'md5sum': local_hash, 'location': local_path })

class GameConfUpdateHandler(http.server.BaseHTTPRequestHandler):
	"""
	Parses form data from a POST request.
	SourceMod itself seems to use multipart requests, but the server accepts both.
	"""
	def parse_form_data(self):
		# https://stackoverflow.com/a/4233452
		# https://stackoverflow.com/a/54705024
		ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
		if ctype == 'multipart/form-data':
			pdict.update({
				'CONTENT-LENGTH': int(self.headers.get('Content-length')),
				'boundary': bytes(pdict['boundary'], "utf-8")
			})
			
			# transform into name, value pairs from name, dict(value)
			return { k: v[0] for k, v in cgi.parse_multipart(self.rfile, pdict).items() }
		elif ctype == 'application/x-www-form-urlencoded':
			length = int(self.headers.get('content-length'))
			return dict(urllib.parse.parse_qsl(self.rfile.read(length).decode('ascii')))
		return {}
	
	# SourceMod sends data as a POST to the URL defined as "AutoUpdateURL" in core.cfg
	def do_POST(self):
		# SourceMod even requests gameconf files via POST (?!); route request to do_GET
		if self.path != '/':
			return self.do_GET()
		
		data = self.parse_form_data()
		
		self.send_response(200)
		self.end_headers()
		
		if not data:
			errors = {
				"error": "Failed to parse request."
			}
			self.wfile.write(vdf.dumps({ 'Errors': errors }, pretty = True).encode('ascii'))
			return
		
		sm_version = tuple(map(int, data.get('version').split('.')))
		
		# TODO should we just do directory checks for this?
		if sm_version < (1, 6) or sm_version >= (1, 12):
			errors = { "error": "Unsupported SourceMod version. Please upgrade." }
			self.wfile.write(vdf.dumps({ 'Errors': errors }, pretty = True).encode('ascii'))
			return
		
		changes = {}
		for name, info in get_changed_gameconf(sm_version, { data[f'file_{n}_name']: data[f'file_{n}_md5'] for n in range(int(data['files'])) }):
			changes[name] = info
		
		self.wfile.write(vdf.dumps({ 'Changed': changes }, pretty = True).encode('ascii'))
	
	# SourceMod requests individual gameconf files
	def do_GET(self):
		# TODO send file on /, else lookup gameconf file
		request_path = os.path.realpath(self.path[1:])
		
		current_directory = os.path.dirname(os.path.realpath(__file__))
		if os.path.commonprefix([request_path, current_directory]) != current_directory:
			self.send_response(403)
			self.send_header('Content-type', 'text/plain')
			self.end_headers()
			return
		
		_, request_ext = os.path.splitext(request_path)
		if not os.path.exists(request_path) or not os.path.isfile(request_path) or request_ext != '.txt':
			self.send_response(404)
			self.send_header('Content-type', 'text/plain')
			self.end_headers()
			return
		
		# TODO sanitize and only access gameconf directories
		self.send_response(200)
		self.send_header('Content-type', 'text/plain')
		self.end_headers()
		
		with open(request_path, 'rb') as gameconf:
			shutil.copyfileobj(gameconf, self.wfile)

if __name__ == '__main__':
	config.read('config.ini')
	host_addr = config.get('server', 'host', fallback = '')
	host_port = config.getint('server', 'port', fallback = 0x4D53)
	
	try:
		server = http.server.HTTPServer((host_addr, host_port), GameConfUpdateHandler)
		print('Started server on host "' + host_addr + '", port', host_port)
		server.serve_forever()
	except KeyboardInterrupt:
		server.socket.close()
