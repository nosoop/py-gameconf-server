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
