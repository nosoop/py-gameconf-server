__version__ = '0.1.1'

# 
# HTTP server that serves gameconf requests from SourceMod installations.
# 

import http.server
import urllib.parse
import urllib.request
import vdf
import itertools
import os
import shutil
import hashlib
import cgi
import cachetools
import pathlib

import configparser
config = configparser.ConfigParser()

"""
Returns a cached value if the file modification time has not changed.
"""
class FileModTimeCache(cachetools.LRUCache):
	def __init__(self, *args, **kwargs):
		self.mtime_cache = {}
		super().__init__(*args, **kwargs)
	
	def __getitem__(self, key):
		if self.mtime_cache.get(key) != os.stat(key).st_mtime:
			self.__missing__(key)
		return super().__getitem__(key)
	
	def __setitem__(self, key, value):
		super().__setitem__(key, value)
		self.mtime_cache[key] = os.stat(key).st_mtime
	
	def popitem(self):
		key, value = super().popitem()
		self.mtime_cache.pop(key)
		return key, value

@cachetools.cached(cache = FileModTimeCache(maxsize = 1024), key = lambda *a: a[0])
def get_md5sum_str(file_path):
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
An iterator for files within the given root_dir and its subdirectories.
"""
def iter_dir_files(root_dir):
	if not root_dir.exists() or not root_dir.is_dir():
		return
	
	for p in root_dir.iterdir():
		if p.is_dir():
			yield from p.iterdir()
		elif p.is_file():
			yield p

"""
Returns a gameconf dir string based on version (e.g., "1.10")
"""
def sm_gameconf_dir(sm_version):
	return '.'.join(map(str, sm_version[:2]))

"""
Given a dict mapping remote files to remote hashes, yield tuple (path, hash, location) with
destination filename and md5 / URL path.

Note that the submitted_files include the 'gamedata/' prefix, but the returned path does not.
"""
def get_changed_gameconf(sm_version, submitted_files):
	# strip gamedata prefix from POST data
	remote_files = { os.path.relpath(f, 'gamedata'): s for f, s in submitted_files.items() }
	
	gameconf_dirs = [ sm_gameconf_dir(sm_version), 'thirdparty' ]
	
	for local_path in itertools.chain.from_iterable(iter_dir_files(pathlib.Path(f)) for f in gameconf_dirs):
		# strip leading dir from our FS path to match remote_files
		remote_path = pathlib.Path(*local_path.parts[1:])
		remote_hash = remote_files.get(str(remote_path))
		if not remote_hash:
			continue
		
		local_hash = get_md5sum_str(local_path)
		if remote_hash == local_hash:
			continue
		
		# always return destination path as posix to avoid transmitting backslashes
		yield pathlib.PurePosixPath(*remote_path.parts), local_hash, urllib.request.pathname2url(str(local_path))

"""
Returns True if path `p` is within root.
"""
def is_path_under(root, p):
	return pathlib.Path(*os.path.commonprefix([p.parts, root.parts])) != root

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
	
	def write_vdf_response(self, data):
		self.wfile.write(vdf.dumps(data, pretty = True).encode('ascii'))
	
	def send_attribution(self):
		self.send_header('X-GCUP-Src', config.get('attribution', 'source'))
	
	def send_plaintext_headers(self, code):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
		self.send_attribution()
		self.end_headers()
	
	# SourceMod sends data as a POST to the URL defined as "AutoUpdateURL" in core.cfg
	def do_POST(self):
		# SourceMod even requests gameconf files via POST (?!); route request to do_GET
		if self.path != '/':
			return self.do_GET()
		
		data = self.parse_form_data()
		
		self.send_plaintext_headers(code = 200)
		
		if not data:
			errors = { "error": "Failed to parse request." }
			self.write_vdf_response({ 'Errors': errors })
			return
		
		sm_version = tuple(map(int, data.get('version').split('.')))
		
		# TODO should we just do directory checks for this?
		if sm_version < (1, 6) or sm_version >= (1, 12):
			errors = { "error": "Unsupported SourceMod version. Please upgrade." }
			self.write_vdf_response({ 'Errors': errors })
			return
		
		changes = {}
		for name, new_hash, location in get_changed_gameconf(sm_version, { data[f'file_{n}_name']: data[f'file_{n}_md5'] for n in range(int(data['files'])) }):
			changes[name] = { 'md5sum': new_hash, 'location': location }
		
		self.write_vdf_response({ 'Changed': changes })
	
	# SourceMod requests individual gameconf files
	def do_GET(self):
		request_path = pathlib.Path(urllib.request.url2pathname(self.path[1:])).resolve()
		
		# prevent path traversal attacks
		if is_path_under(pathlib.Path.cwd(), request_path):
			self.send_plaintext_headers(code = 403)
			return
		
		if not request_path.is_file() or request_path.suffix != '.txt':
			self.send_plaintext_headers(code = 404)
			return
		
		# TODO sanitize and only access gameconf directories
		self.send_plaintext_headers(code = 200)
		
		with request_path.open('rb') as gameconf:
			shutil.copyfileobj(gameconf, self.wfile)

def main():
	import argparse
	parser = argparse.ArgumentParser(description = "Runs a SM game config update server.")
	parser.add_argument('--config', help = "Configuration file to use.", type = pathlib.Path,
			default = 'config.ini')
	
	args = parser.parse_args()
	
	if not args.config.exists() or not args.config.is_file():
		# The configuration file must exist somewhere.
		raise Exception("Missing server configuration file.")
	
	config.read(args.config)
	
	if not config.get('attribution', 'source', fallback = None):
		raise Exception("Missing attribution / source section in configuration file.")
	
	new_root = config.get('server', 'workdir', fallback = None)
	if new_root:
		if not os.path.isabs(new_root):
			new_root = args.config.parent / new_root
		os.chdir(os.path.abspath(new_root))
		
	print(f"Set working directory to '{os.getcwd()}'")
	
	host_addr = config.get('server', 'host', fallback = '')
	host_port = config.getint('server', 'port', fallback = 0x4D53)
	
	try:
		server = http.server.HTTPServer((host_addr, host_port), GameConfUpdateHandler)
		print(f"Started server on host '{host_addr}', port {host_port}")
		server.serve_forever()
	except KeyboardInterrupt:
		server.socket.close()

if __name__ == '__main__':
	main()
