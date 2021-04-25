# -*- coding: utf-8 -*-
"""
	Venom Add-on
"""

from ast import literal_eval
from hashlib import md5
from re import sub as re_sub
from time import time
try: from sqlite3 import dbapi2 as db
except ImportError: from pysqlite2 import dbapi2 as db
from resources.lib.modules import control
from resources.lib.modules import log_utils


def get(function, duration, *args):
	"""
	:param function: Function to be executed
	:param duration: Duration of validity of cache in hours
	:param args: Optional arguments for the provided function
	"""
	try:
		key = _hash_function(function, args)
		cache_result = cache_get(key)
		if cache_result:
			result = literal_eval(cache_result['value'])
			if _is_cache_valid(cache_result['date'], duration):
				return result

		fresh_result = repr(function(*args)) # may need a try-except block for server timeouts
		try:  # Sometimes None is returned as a string instead of None type for "fresh_result"
			invalid = False
			if not fresh_result: invalid = True
			elif fresh_result == 'None' or fresh_result == '' or fresh_result == '[]' or fresh_result == '{}': invalid = True
			elif len(fresh_result) == 0: invalid = True
		except: pass

		if invalid: # If the cache is old, but we didn't get "fresh_result", return the old cache
			if cache_result: return result
			else: return None
		else:
			cache_insert(key, fresh_result)
			return literal_eval(fresh_result)
	except:
		log_utils.error()
		return None

def _is_cache_valid(cached_time, cache_timeout):
	now = int(time())
	diff = now - cached_time
	return (cache_timeout * 3600) > diff

def timeout(function, *args):
	try:
		key = _hash_function(function, args)
		result = cache_get(key)
		return int(result['date']) if result else 0
	except:
		log_utils.error()
		return 0

def cache_existing(function, *args):
	try:
		cache_result = cache_get(_hash_function(function, args))
		if cache_result: return literal_eval(cache_result['value'])
		else: return None
	except:
		log_utils.error()
		return None

def cache_get(key):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		ck_table = dbcur.execute('''SELECT * FROM sqlite_master WHERE type='table' AND name='cache';''').fetchone()
		if not ck_table: return None
		results = dbcur.execute('''SELECT * FROM cache WHERE key=?''', (key,)).fetchone()
		return results
	except:
		log_utils.error()
		return None
	finally:
		dbcur.close() ; dbcon.close()

def cache_insert(key, value):
	try:
		dbcon = get_connection()
		dbcur = get_connection_cursor(dbcon)
		now = int(time())
		dbcur.execute('''CREATE TABLE IF NOT EXISTS cache (key TEXT, value TEXT, date INTEGER, UNIQUE(key));''')
		update_result = dbcur.execute('''UPDATE cache SET value=?,date=? WHERE key=?''', (value, now, key))
		if update_result.rowcount == 0:
			dbcur.execute('''INSERT INTO cache Values (?, ?, ?)''', (key, value, now))
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()

def _hash_function(function_instance, *args):
	return _get_function_name(function_instance) + _generate_md5(args)

def _get_function_name(function_instance):
	return re_sub(r'.+\smethod\s|.+function\s|\sat\s.+|\sof\s.+', '', repr(function_instance))

def _generate_md5(*args):
	md5_hash = md5()
	try: [md5_hash.update(str(arg)) for arg in args]
	except: [md5_hash.update(str(arg).encode('utf-8')) for arg in args]
	return str(md5_hash.hexdigest())

def cache_clear():
	dbcon = get_connection()
	dbcur = get_connection_cursor(dbcon)
	for t in ['cache', 'rel_list', 'rel_lib']:
		try:
			dbcur.execute('''DROP TABLE IF EXISTS {}'''.format(t))
			dbcur.execute('''VACUUM''')
			dbcur.connection.commit()
		except:
			log_utils.error()
	try: dbcur.close() ; dbcon.close()
	except: pass
	return True

def get_connection():
	if not control.existsPath(control.dataPath): control.makeFile(control.dataPath)
	dbcon = db.connect(control.cacheFile, timeout=60) # added timeout 3/23/21 for concurrency with threads
	dbcon.row_factory = _dict_factory
	return dbcon

def get_connection_cursor(dbcon):
	dbcur = dbcon.cursor()
	dbcur.execute('''PRAGMA synchronous = OFF''')
	dbcur.execute('''PRAGMA journal_mode = OFF''')
	return dbcur

def _dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description): d[col[0]] = row[idx]
	return d

##################
def cache_clear_search():
	cleared = False
	try:
		dbcon = get_connection_search()
		dbcur = dbcon.cursor()
		for t in ['tvshow', 'movies']:
			dbcur.execute('''DROP TABLE IF EXISTS {}'''.format(t))
			dbcur.execute('''VACUUM''')
			dbcur.connection.commit()
			control.refresh()
			cleared = True
	except:
		log_utils.error()
		cleared = False
	finally:
		dbcur.close() ; dbcon.close()
	return cleared

def cache_clear_SearchPhrase(table, key):
	cleared = False
	try:
		dbcon = get_connection_search()
		dbcur = dbcon.cursor()
		dbcur.execute('''DELETE FROM {} WHERE term=?;'''.format(table), (key,))
		dbcur.connection.commit()
		control.refresh()
		cleared = True
	except:
		log_utils.error()
		cleared = False
	finally:
		dbcur.close() ; dbcon.close()
	return cleared

def get_connection_search():
	control.makeFile(control.dataPath)
	conn = db.connect(control.searchFile)
	conn.row_factory = _dict_factory
	return conn
##################
def cache_clear_bookmarks():
	cleared = False
	try:
		dbcon = get_connection_bookmarks()
		dbcur = dbcon.cursor()
		dbcur.execute('''DROP TABLE IF EXISTS bookmark''')
		dbcur.execute('''VACUUM''')
		dbcur.connection.commit()
		cleared = True
	except:
		log_utils.error()
		cleared = False
	finally:
		dbcur.close() ; dbcon.close()
	return cleared

def cache_clear_bookmark(name, year='0'):
	cleared = False
	try:
		dbcon = get_connection_bookmarks()
		dbcur = dbcon.cursor()
		# idFile = md5()
		# for i in name: idFile.update(str(i))
		# for i in year: idFile.update(str(i))
		# idFile = str(idFile.hexdigest())
		# dbcur.execute("DELETE FROM bookmark WHERE idFile = '%s'" % idFile)
		years = [str(year), str(int(year)+1), str(int(year)-1)]
		dbcur.execute('''DELETE FROM bookmark WHERE Name="%s" AND year IN (%s)''' % (name, ','.join(i for i in years)))
		dbcur.connection.commit()
		control.refresh()
		control.trigger_widget_refresh()
		cleared = True
	except:
		log_utils.error()
		cleared = False
	finally:
		dbcur.close() ; dbcon.close()
	return cleared

def get_connection_bookmarks():
	control.makeFile(control.dataPath)
	conn = db.connect(control.bookmarksFile)
	conn.row_factory = _dict_factory
	return conn
##################
def clear_local_bookmarks(): # clear all venom bookmarks from kodi database
	try:
		dbcon = db.connect(control.get_video_database_path())
		dbcur = dbcon.cursor()
		dbcur.execute('''SELECT * FROM files WHERE strFilename LIKE "%plugin.video.venom%"''')
		file_ids = [str(i[0]) for i in dbcur.fetchall()]
		for table in ["bookmark", "streamdetails", "files"]:
			dbcur.execute('''DELETE FROM {} WHERE idFile IN ({})'''.format(table, ','.join(file_ids)))
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()

def clear_local_bookmark(url): # clear all item specific bookmarks from kodi database
	try:
		dbcon = db.connect(control.get_video_database_path())
		dbcur = dbcon.cursor()
		dbcur.execute('''SELECT * FROM files WHERE strFilename LIKE "%{}%"'''.format(url))
		file_ids = [str(i[0]) for i in dbcur.fetchall()]
		if not file_ids: return
		for table in ["bookmark", "streamdetails", "files"]:
			dbcur.execute('''DELETE FROM {} WHERE idFile IN ({})'''.format(table, ','.join(file_ids)))
		dbcur.connection.commit()
	except:
		log_utils.error()
	finally:
		dbcur.close() ; dbcon.close()
##################
def cache_version_check():
	try:
		if _find_cache_version():
			# cache_clear_all()
			from resources.lib.database import providerscache, metacache
			providerscache.cache_clear_providers()
			metacache.cache_clear_meta()
			cache_clear()
			cache_clear_search()
			cache_clear_bookmarks()
			control.notification(message=32057)
	except:
		log_utils.error()

def _find_cache_version():
	versionFile = control.joinPath(control.dataPath, 'cache.v')
	try:
		if not control.existsPath(versionFile):
			f = open(versionFile, 'w')
			f.close()
	except:
		log_utils.log('Venom Addon Data Path Does not Exist. Creating Folder....', __name__, log_utils.LOGDEBUG)
		ad_folder = control.transPath('special://profile/addon_data/plugin.video.venom')
		control.makeDirs(ad_folder)
	try:
		with open(versionFile, 'r') as fh: oldVersion = fh.read()
	except: oldVersion = '0'
	try:
		curVersion = control.addon('plugin.video.venom').getAddonInfo('version')
		if oldVersion != curVersion:
			with open(versionFile, 'w') as fh: 	fh.write(curVersion)
			return True
		else: return False
	except:
		log_utils.error()
		return False