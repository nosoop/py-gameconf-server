__version__ = '0.1.1'

# 
# HTTP server that serves gameconf requests from SourceMod installations.
# 

import http.server
import urllib.parse
import urllib.request
import vdf
import os
import shutil
import cgi
import pathlib

import configparser
config = configparser.ConfigParser()

import gameconf_server.server
gc_server = gameconf_server.server.GameConfigServer()

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
	
	def send_plaintext_headers(self, code):
		self.send_response(code)
		self.send_header('Content-Type', 'text/plain')
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
		
		response = gc_server.process_request(data)
		self.write_vdf_response(response)
	
	# SourceMod requests individual gameconf files
	def do_GET(self):
		# strip leading '/' to turn into a relative path component
		request_path = gc_server.get_gameconf_file_path(
			urllib.request.url2pathname(self.path[1:])
		)
		
		if not request_path:
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
	
	# mount known game config directories for future iteration
	# TODO this is hardcoded temporarily - move this into the config or something
	gc_server.directories = {
		"1.10": gameconf_server.server.SourceModVersionedGameConfigDirectory('1.10', (1, 10)),
		"1.11": gameconf_server.server.SourceModVersionedGameConfigDirectory('1.11', (1, 11)),
		"thirdparty": gameconf_server.server.GameConfigDirectory('thirdparty'),
	}
	
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
