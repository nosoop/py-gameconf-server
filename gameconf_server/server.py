import hashlib
import os
import pathlib
import urllib

class GameConfigDirectory:
	def __init__(self, path):
		self.path = pathlib.Path(path)
		
		# name -> (last_mtime, md5sum)
		self.md5sums = {}
	
	def valid_directory(self, data):
		return True
	
	def _get_file_hash_impl(self, target):
		if not target.exists():
			return None
		try:
			hasher = hashlib.md5()
			with (target).open('rb') as f:
				for chunk in iter(lambda: f.read(4096), b''):
					hasher.update(chunk)
				return hasher.hexdigest()
		except (PermissionError) as e:
			pass
		return None
	
	def get_file_hash(self, file_path):
		# given the name of a file under gamedata/ (excluding prefix),
		# return the hash of the file
		cached_mtime, cached_md5sum = self.md5sums.get(file_path, (0, None))
		
		target = self.path / file_path
		if not target.exists():
			return None
		
		mtime = os.path.getmtime(target)
		
		if mtime > cached_mtime or cached_md5sum is None:
			self.md5sums[file_path] = (mtime, self._get_file_hash_impl(target))
		
		_, hash = self.md5sums.get(file_path, (0, None))
		return hash

class SourceModVersionedGameConfigDirectory(GameConfigDirectory):
	def __init__(self, path, required_version):
		super().__init__(path)
		self.required_version = required_version # tuple
	
	def valid_directory(self, data):
		input_version = self.extract_version(data)
		
		# the input version must be at least as precise as the version specified for this entry
		# we only test as many values as given
		required_sig = len(self.required_version)
		return len(input_version) >= len(self.required_version) and input_version[:required_sig] == self.required_version
	
	def extract_version(self, data):
		version_str = data.get('version')
		if not version_str:
			return None
		return tuple(map(int, version_str.split('.')))

class GameConfigServer:
	def __init__(self):
		# mapping the name of a 'virtual directory' to a physical directory
		self.directories = {}
	
	def process_request(self, data):
		# takes a list of key / value pairs (dict / multidict) as sent from the gameconf client,
		# and responds with a dict (upstream represents this as a VDF / SMC text)
		
		changes = {}
		
		num_files = int(data.get('files'))
		for n in range(num_files):
			file_name, file_md5 = data.get(f'file_{n}_name'), data.get(f'file_{n}_md5')
			
			if not file_name or not file_md5:
				continue
			
			file_path = pathlib.Path(file_name)
			if not file_path.is_relative_to('gamedata'):
				continue
			
			file_path = file_path.relative_to('gamedata')
			
			local_hash, local_path = None, None
			for mount_prefix, gcdir in self.directories.items():
				if not gcdir.valid_directory(data):
					continue
				
				local_hash, local_path = gcdir.get_file_hash(file_path), mount_prefix / file_path
				if local_hash:
					break
			
			if not local_hash or file_md5 == local_hash:
				continue
			
			# always return destination path as posix to avoid transmitting backslashes
			changes[str(pathlib.PurePosixPath(file_path))] = {
				'md5sum': local_hash,
				'location': urllib.request.pathname2url(str(local_path)),
			}
		
		return { 'Changed': changes }
	
	def get_gameconf_file_path(self, target_path):
		"""
		Given a relative URL input path, returns the path of the file on disk.
		"""
		mount_prefix, *subpath = pathlib.Path(target_path).parts
		gcdir = self.directories.get(mount_prefix)
		if not gcdir:
			return None
		
		result_path = (gcdir.path / pathlib.Path(*subpath))
		
		if os.path.commonpath(os.path.abspath(p) for p in (result_path, gcdir.path)) != str(gcdir.path.resolve()):
			# prevent path traversal attack
			# os.path.abspath is used over pathlib.Path.resolve to allow for symlinks
			return None
		
		if not result_path.is_file() or result_path.suffix != '.txt':
			return None
		
		return result_path
