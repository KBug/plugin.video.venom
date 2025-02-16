# -*- coding: utf-8 -*-
"""
	Venom Add-on
"""

from datetime import datetime, timedelta
from json import dumps as jsdumps
import re
from threading import Thread
from urllib.parse import quote_plus, urlencode, parse_qsl, urlparse, urlsplit
from resources.lib.database import cache, metacache, fanarttv_cache, traktsync
from resources.lib.indexers.tmdb import Movies as tmdb_indexer
from resources.lib.indexers.fanarttv import FanartTv
from resources.lib.modules import cleangenre
from resources.lib.modules import client
from resources.lib.modules import control
from resources.lib.modules.playcount import getMovieIndicators, getMovieOverlay
from resources.lib.modules import tools
from resources.lib.modules import trakt
from resources.lib.modules import views

getLS = control.lang
getSetting = control.setting


class Movies:
	def __init__(self, notifications=True):
		self.list = []
		self.page_limit = getSetting('page.item.limit')
		self.search_page_limit = getSetting('search.page.limit')
		self.notifications = notifications
		self.date_time = datetime.now()
		self.today_date = (self.date_time).strftime('%Y-%m-%d')
		self.hidecinema = getSetting('hidecinema') == 'true'
		self.trakt_user = getSetting('trakt.username').strip()
		self.traktCredentials = trakt.getTraktCredentialsInfo()
		self.lang = control.apiLanguage()['trakt']
		self.imdb_user = getSetting('imdb.user').replace('ur', '')
		self.tmdb_key = getSetting('tmdb.api.key')
		if not self.tmdb_key: self.tmdb_key = '3320855e65a9758297fec4f7c9717698'
		self.tmdb_session_id = getSetting('tmdb.session_id')
		# self.user = str(self.imdb_user) + str(self.tmdb_key)
		self.user = str(self.tmdb_key)
		self.enable_fanarttv = getSetting('enable.fanarttv') == 'true'
		self.prefer_tmdbArt = getSetting('prefer.tmdbArt') == 'true'
		self.unairedcolor = control.getColor(getSetting('movie.unaired.identify'))
		self.highlight_color = control.getHighlightColor()
		self.tmdb_link = 'https://api.themoviedb.org'
		self.tmdb_popular_link = 'https://api.themoviedb.org/3/movie/popular?api_key=%s&language=en-US&region=US&page=1'
		self.tmdb_toprated_link = 'https://api.themoviedb.org/3/movie/top_rated?api_key=%s&page=1'
		self.tmdb_upcoming_link = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&primary_release_date.gte=%s&with_release_type=3|2|1&sort_by=popularity.desc&page=1' % ('%s', (self.date_time + timedelta(days=1)).strftime('%Y-%m-%d'))
		self.tmdb_nowplaying_link = 'https://api.themoviedb.org/3/movie/now_playing?api_key=%s&language=en-US&region=US&page=1'
		self.tmdb_boxoffice_link = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&sort_by=revenue.desc&page=1'
		self.tmdb_userlists_link = 'https://api.themoviedb.org/3/account/{account_id}/lists?api_key=%s&language=en-US&session_id=%s&page=1' % ('%s', self.tmdb_session_id) # used by library import only
		self.tmdb_genre_link = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&primary_release_date.lte=%s&with_genres=%s&sort_by=%s&page=1' % ('%s', self.today_date, '%s', self.tmdb_DiscoverSort())
		self.tmdb_year_link = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&primary_release_date.lte=%s&certification_country=US&primary_release_year=%s&sort_by=%s&page=1' % ('%s', self.today_date, '%s', self.tmdb_DiscoverSort())
		self.tmdb_certification_link = 'https://api.themoviedb.org/3/discover/movie?api_key=%s&language=en-US&region=US&primary_release_date.lte=%s&certification_country=US&certification=%s&sort_by=%s&page=1' % ('%s', self.today_date, '%s', self.tmdb_DiscoverSort())

		self.imdb_link = 'https://www.imdb.com'
		self.persons_link = 'https://www.imdb.com/search/name/?count=100&name='
		self.personlist_link = 'https://www.imdb.com/search/name/?count=100&gender=male,female'
		self.person_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&production_status=released&role=%s&sort=year,desc&count=%s&start=1' % ('%s', self.page_limit)
		self.keyword_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie,documentary&num_votes=100,&keywords=%s&sort=%s&count=%s&start=1' % ('%s', self.imdb_sort(), self.page_limit)
		self.oscars_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&production_status=released&groups=oscar_best_picture_winners&sort=year,desc&count=%s&start=1' % self.page_limit
		self.oscarsnominees_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&production_status=released&groups=oscar_best_picture_nominees&sort=year,desc&count=%s&start=1' % self.page_limit
		self.theaters_link = 'https://www.imdb.com/search/title/?title_type=feature&num_votes=500,&release_date=date[90],date[0]&languages=en&sort=release_date,desc&count=%s&start=1' % self.page_limit
		self.imdb_comingsoon_link = 'https://www.imdb.com/movies-coming-soon/'
		self.year_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=100,&production_status=released&year=%s,%s&sort=moviemeter,asc&count=%s&start=1' % ('%s', '%s', self.page_limit)
		if self.hidecinema:
			hidecinema_rollback = str(int(getSetting('hidecinema.rollback')) * 30)
			self.mostpopular_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&groups=top_1000&release_date=,date[%s]&sort=moviemeter,asc&count=%s&start=1' % (hidecinema_rollback, self.page_limit )
			self.mostvoted_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&release_date=,date[%s]&sort=num_votes,desc&count=%s&start=1' % (hidecinema_rollback, self.page_limit )
			self.featured_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&release_date=,date[%s]&sort=moviemeter,asc&count=%s&start=1' % (hidecinema_rollback, self.page_limit )
			self.genre_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie,documentary&num_votes=3000,&release_date=,date[%s]&genres=%s&sort=%s&count=%s&start=1' % (hidecinema_rollback, '%s', self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.language_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=100,&production_status=released&primary_language=%s&release_date=,date[%s]&sort=%s&count=%s&start=1' % ('%s', hidecinema_rollback, self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.certification_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=100,&production_status=released&certificates=%s&release_date=,date[%s]&sort=%s&count=%s&start=1' % ('%s', hidecinema_rollback, self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.imdbboxoffice_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&production_status=released&sort=boxoffice_gross_us,desc&release_date=,date[%s]&count=%s&start=1' % (hidecinema_rollback, self.page_limit)
		else:
			self.mostpopular_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&groups=top_1000&sort=moviemeter,asc&count=%s&start=1' % self.page_limit
			self.mostvoted_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&sort=num_votes,desc&count=%s&start=1' % self.page_limit
			self.featured_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=1000,&production_status=released&sort=moviemeter,asc&count=%s&start=1' % self.page_limit
			self.genre_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie,documentary&num_votes=3000,&release_date=,date[0]&genres=%s&sort=%s&count=%s&start=1' % ('%s', self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.language_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=100,&production_status=released&primary_language=%s&sort=%s&count=%s&start=1' % ('%s', self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.certification_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&num_votes=100,&production_status=released&certificates=%s&sort=%s&count=%s&start=1' % ('%s', self.imdb_sort(type='imdbmovies'), self.page_limit)
			self.imdbboxoffice_link = 'https://www.imdb.com/search/title/?title_type=feature,tv_movie&production_status=released&sort=boxoffice_gross_us,desc&count=%s&start=1' % self.page_limit
		self.imdbwatchlist_link = 'https://www.imdb.com/user/ur%s/watchlist?sort=date_added,desc' % self.imdb_user # only used to get users watchlist ID
		self.imdbwatchlist2_link = 'https://www.imdb.com/list/%s/?view=detail&sort=%s&title_type=movie,short,video,tvShort,tvMovie,tvSpecial&start=1' % ('%s', self.imdb_sort(type='movies.watchlist'))
		self.imdblists_link = 'https://www.imdb.com/user/ur%s/lists?tab=all&sort=mdfd&order=desc&filter=titles' % self.imdb_user
		self.imdblist_link = 'https://www.imdb.com/list/%s/?view=detail&sort=%s&title_type=movie,short,video,tvShort,tvMovie,tvSpecial&start=1' % ('%s', self.imdb_sort())
		self.imdbratings_link = 'https://www.imdb.com/user/ur%s/ratings?sort=your_rating,desc&mode=detail&start=1' % self.imdb_user # IMDb ratings does not take title_type so filter is in imdb_list() function
		self.anime_link = 'https://www.imdb.com/search/keyword/?keywords=anime&title_type=movie,tvMovie&release_date=,date[0]&sort=moviemeter,asc&count=%s&start=1' % self.page_limit

		self.trakt_link = 'https://api.trakt.tv'
		self.search_link = 'https://api.trakt.tv/search/movie?limit=%s&page=1&query=' % self.search_page_limit
		self.traktlistsearch_link = 'https://api.trakt.tv/search/list?limit=%s&page=1&query=' % self.page_limit
		self.traktlists_link = 'https://api.trakt.tv/users/me/lists'
		self.traktlikedlists_link = 'https://api.trakt.tv/users/likes/lists?limit=1000000' # used by library import only
		self.traktwatchlist_link = 'https://api.trakt.tv/users/me/watchlist/movies?limit=%s&page=1' % self.page_limit # this is now a dummy link for pagination to work
		self.traktcollection_link = 'https://api.trakt.tv/users/me/collection/movies?limit=%s&page=1' % self.page_limit # this is now a dummy link for pagination to work
		self.trakthistory_link = 'https://api.trakt.tv/users/me/history/movies?limit=%s&page=1' % self.page_limit
		self.traktlist_link = 'https://api.trakt.tv/users/%s/lists/%s/items/movies?limit=%s&page=1' % ('%s', '%s', self.page_limit) # local pagination, limit and page used to advance, pulled from request
		self.traktunfinished_link = 'https://api.trakt.tv/sync/playback/movies?limit=40'
		self.traktanticipated_link = 'https://api.trakt.tv/movies/anticipated?limit=%s&page=1' % self.page_limit 
		self.trakttrending_link = 'https://api.trakt.tv/movies/trending?limit=%s&page=1' % self.page_limit
		self.traktboxoffice_link = 'https://api.trakt.tv/movies/boxoffice' # Returns the top 10 grossing movies in the U.S. box office last weekend
		self.traktpopular_link = 'https://api.trakt.tv/movies/popular?limit=%s&page=1' % self.page_limit
		self.traktrecommendations_link = 'https://api.trakt.tv/recommendations/movies?limit=40'
		self.trakt_popularLists_link = 'https://api.trakt.tv/lists/popular?limit=%s&page=1' % self.page_limit
		self.trakt_trendingLists_link = 'https://api.trakt.tv/lists/trending?limit=%s&page=1' % self.page_limit

	def get(self, url, idx=True, create_directory=True):
		self.list = []
		try:
			try: url = getattr(self, url + '_link')
			except: pass
			try: u = urlparse(url).netloc.lower()
			except: pass
			if u in self.trakt_link and '/users/' in url:
				try:
					isTraktHistory = (url.split('&page=')[0] in self.trakthistory_link)
					if '/users/me/' not in url: raise Exception()
					if '/collection/' in url: return self.traktCollection(url)
					if '/watchlist/' in url: return self.traktWatchlist(url)
					if trakt.getActivity() > cache.timeout(self.trakt_list, url, self.trakt_user):
						self.list = cache.get(self.trakt_list, 0, url, self.trakt_user)
					else: self.list = cache.get(self.trakt_list, 720, url, self.trakt_user)
				except:
					self.list = self.trakt_userList(url)
				if isTraktHistory and self.list:
					for i in range(len(self.list)): self.list[i]['traktHistory'] = True
				if idx: self.worker()
				if not isTraktHistory: self.sort()
			elif u in self.trakt_link and self.search_link in url:
				self.list = cache.get(self.trakt_list, 6, url, self.trakt_user)
				if idx: self.worker()
			elif u in self.trakt_link:
				self.list = cache.get(self.trakt_list, 24, url, self.trakt_user)
				if idx: self.worker()
			elif u in self.imdb_link and ('/user/' in url or '/list/' in url):
				isRatinglink = True if self.imdbratings_link in url else False
				self.list = cache.get(self.imdb_list, 0, url, isRatinglink)
				if idx: self.worker()
				# self.sort() # switched to request sorting for imdb
			elif u in self.imdb_link:
				if 'coming-soon' in url:
					self.list = cache.get(self.imdb_list, 96, url, True)
				else: self.list = cache.get(self.imdb_list, 96, url)
				if idx: self.worker()
			if self.list is None: self.list = []
			if idx and create_directory: self.movieDirectory(self.list)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			if not self.list:
				control.hide()
				if self.notifications: control.notification(title=32001, message=33049)

	def getTMDb(self, url, create_directory=True):
		self.list = []
		try:
			try: url = getattr(self, url + '_link')
			except: pass
			try: u = urlparse(url).netloc.lower()
			except: pass
			if u in self.tmdb_link and '/list/' in url:
				self.list = tmdb_indexer().tmdb_collections_list(url) # caching handled in list indexer
				self.sort()
			elif u in self.tmdb_link and '/list/' not in url:
				self.list = tmdb_indexer().tmdb_list(url) # caching handled in list indexer
			if self.list is None: self.list = []
			if create_directory: self.movieDirectory(self.list)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			if not self.list:
				control.hide()
				if self.notifications: control.notification(title=32001, message=33049)

	def getTraktPublicLists(self, url, create_directory=True):
		self.list = []
		try:
			try: url = getattr(self, url + '_link')
			except: pass
			if '/popular' in url:
				self.list = cache.get(self.trakt_public_list, 168, url)
			elif '/trending' in url:
				self.list = cache.get(self.trakt_public_list, 48, url)
			else:
				self.list = cache.get(self.trakt_public_list, 24, url)
			if self.list is None: self.list = []
			if create_directory: self.addDirectory(self.list)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def unfinished(self, url, idx=True, create_directory=True):
		self.list = []
		try:
			self.list = traktsync.fetch_bookmarks(imdb='', ret_all=True, ret_type='movies')
			if idx: self.worker()
			self.list = sorted(self.list, key=lambda k: k['paused_at'], reverse=True)
			if self.list is None: self.list = []
			if create_directory: self.movieDirectory(self.list, unfinished=True, next=False)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def unfinishedManager(self):
		try:
			control.busy()
			list = self.unfinished(url='traktunfinished', create_directory=False)
			control.hide()
			from resources.lib.windows.traktmovieprogress_manager import TraktMovieProgressManagerXML
			window = TraktMovieProgressManagerXML('traktmovieprogress_manager.xml', control.addonPath(control.addonId()), results=list)
			selected_items = window.run()
			del window
			if selected_items:
				refresh = 'plugin.video.venom' in control.infoLabel('Container.PluginName')
				trakt.scrobbleResetItems(imdb_ids=selected_items, refresh=refresh, widgetRefresh=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def collectionManager(self):
		try:
			control.busy()
			self.list = traktsync.fetch_collection('movies_collection')
			self.worker()
			self.sort()
			# self.list = sorted(self.list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['tvshowtitle'].lower()), reverse=False)
			control.hide()
			from resources.lib.windows.traktbasic_manager import TraktBasicManagerXML
			window = TraktBasicManagerXML('traktbasic_manager.xml', control.addonPath(control.addonId()), results=self.list)
			selected_items = window.run()
			del window
			if selected_items:
				# refresh = 'plugin.video.venom' in control.infoLabel('Container.PluginName')
				trakt.removeCollectionItems('movies', selected_items)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			control.hide()

	def watchlistManager(self):
		try:
			control.busy()
			self.list = traktsync.fetch_watch_list('movies_watchlist')
			self.worker()
			self.sort(type='movies.watchlist')
			# self.list = sorted(self.list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['tvshowtitle'].lower()), reverse=False)
			control.hide()
			from resources.lib.windows.traktbasic_manager import TraktBasicManagerXML
			window = TraktBasicManagerXML('traktbasic_manager.xml', control.addonPath(control.addonId()), results=self.list)
			selected_items = window.run()
			del window
			if selected_items:
				# refresh = 'plugin.video.venom' in control.infoLabel('Container.PluginName')
				trakt.removeWatchlistItems('movies', selected_items)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			control.hide()

	def likedListsManager(self):
		try:
			items = traktsync.fetch_liked_list('', True)
			from resources.lib.windows.traktlikedlist_manager import TraktLikedListManagerXML
			window = TraktLikedListManagerXML('traktlikedlist_manager.xml', control.addonPath(control.addonId()), results=items)
			selected_items = window.run()
			del window
			if selected_items:
				# refresh = 'plugin.video.venom' in control.infoLabel('Container.PluginName')
				trakt.remove_liked_lists(selected_items)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def sort(self, type='movies'):
		try:
			if not self.list: return
			attribute = int(getSetting('sort.%s.type' % type))
			reverse = int(getSetting('sort.%s.order' % type)) == 1
			if attribute == 0: reverse = False # Sorting Order is not enabled when sort method is "Default"
			if attribute > 0:
				if attribute == 1:
					try: self.list = sorted(self.list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['title'].lower()), reverse=reverse)
					except: self.list = sorted(self.list, key=lambda k: k['title'].lower(), reverse=reverse)
				elif attribute == 2: self.list = sorted(self.list, key=lambda k: float(k['rating']), reverse=reverse)
				elif attribute == 3: self.list = sorted(self.list, key=lambda k: int(str(k['votes']).replace(',', '')), reverse=reverse)
				elif attribute == 4:
					for i in range(len(self.list)):
						if 'premiered' not in self.list[i]: self.list[i]['premiered'] = ''
					self.list = sorted(self.list, key=lambda k: k['premiered'], reverse=reverse)
				elif attribute == 5:
					for i in range(len(self.list)):
						if 'added' not in self.list[i]: self.list[i]['added'] = ''
					self.list = sorted(self.list, key=lambda k: k['added'], reverse=reverse)
				elif attribute == 6:
					for i in range(len(self.list)):
						if 'lastplayed' not in self.list[i]: self.list[i]['lastplayed'] = ''
					self.list = sorted(self.list, key=lambda k: k['lastplayed'], reverse=reverse)
			elif reverse:
				self.list = list(reversed(self.list))
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def imdb_sort(self, type='movies'):
		sort = int(getSetting('sort.%s.type' % type))
		imdb_sort = 'list_order' if type == 'movies.watchlist' else 'moviemeter'
		if sort == 1: imdb_sort = 'alpha'
		elif sort == 2: imdb_sort = 'user_rating'
		elif sort == 3: imdb_sort = 'num_votes'
		elif sort == 4: imdb_sort = 'release_date'
		elif sort in (5, 6): imdb_sort = 'date_added'
		imdb_sort_order = ',asc' if (int(getSetting('sort.%s.order' % type)) == 0 or sort == 0) else ',desc'
		sort_string = imdb_sort + imdb_sort_order
		return sort_string

	def tmdb_DiscoverSort(self):
		sort = int(getSetting('sort.movies.type'))
		tmdb_sort = 'popularity' # default sort=0
		if sort == 1: tmdb_sort = 'title'
		elif sort == 2: tmdb_sort = 'vote_average'
		elif sort == 3: tmdb_sort = 'vote_count'
		elif sort in (4, 5, 6): tmdb_sort = 'primary_release_date'
		tmdb_sort_order = '.asc' if (int(getSetting('sort.movies.order')) == 0) else '.desc'
		sort_string = tmdb_sort + tmdb_sort_order
		if sort == 2: sort_string = sort_string + '&vote_count.gte=500'
		return sort_string

	def search(self):
		from resources.lib.menus import navigator
		navigator.Navigator().addDirectoryItem(getLS(32603) % self.highlight_color, 'movieSearchnew', 'search.png', 'DefaultAddonsSearch.png', isFolder=False)
		from sqlite3 import dbapi2 as database
		try:
			if not control.existsPath(control.dataPath): control.makeFile(control.dataPath)
			dbcon = database.connect(control.searchFile)
			dbcur = dbcon.cursor()
			dbcur.executescript('''CREATE TABLE IF NOT EXISTS movies (ID Integer PRIMARY KEY AUTOINCREMENT, term);''')
			dbcur.execute('''SELECT * FROM movies ORDER BY ID DESC''')
			dbcur.connection.commit()
			lst = []
			delete_option = False
			for (id, term) in sorted(dbcur.fetchall(), key=lambda k: re.sub(r'(^the |^a |^an )', '', k[1].lower()), reverse=False):
				if term not in str(lst):
					delete_option = True
					navigator.Navigator().addDirectoryItem(term, 'movieSearchterm&name=%s' % term, 'search.png', 'DefaultAddonsSearch.png', isSearch=True, table='movies')
					lst += [(term)]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			dbcur.close() ; dbcon.close()
		if delete_option: navigator.Navigator().addDirectoryItem(32605, 'cache_clearSearch', 'tools.png', 'DefaultAddonService.png', isFolder=False)
		navigator.Navigator().endDirectory()

	def search_new(self):
		k = control.keyboard('', getLS(32010))
		k.doModal()
		q = k.getText() if k.isConfirmed() else None
		if not q: return control.closeAll()
		from sqlite3 import dbapi2 as database
		try:
			dbcon = database.connect(control.searchFile)
			dbcur = dbcon.cursor()
			dbcur.execute('''INSERT INTO movies VALUES (?,?)''', (None, q))
			dbcur.connection.commit()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		finally:
			dbcur.close() ; dbcon.close()
		url = self.search_link + quote_plus(q)
		control.closeAll()
		control.execute('ActivateWindow(Videos,plugin://plugin.video.venom/?action=movies&url=%s,return)' % (quote_plus(url)))

	def search_term(self, name):
		url = self.search_link + quote_plus(name)
		self.get(url)

	def person(self):
		k = control.keyboard('', getLS(32010))
		k.doModal()
		q = k.getText().strip() if k.isConfirmed() else None
		if not q: return control.closeAll()
		url = self.persons_link + quote_plus(q)
		control.closeAll()
		control.execute('ActivateWindow(Videos,plugin://plugin.video.venom/?action=moviePersons&url=%s,return)' % (quote_plus(url)))

	def persons(self, url):
		if url is None: self.list = cache.get(self.imdb_person_list, 24, self.personlist_link)
		else: self.list = cache.get(self.imdb_person_list, 1, url)
		if self.list is None: self.list = []
		if self.list:
			for i in range(0, len(self.list)): self.list[i].update({'content': 'actors', 'icon': 'DefaultActor.png', 'action': 'movies'})
		self.addDirectory(self.list)
		return self.list

	def genres(self, url):
		try: url = getattr(self, url + '_link')
		except: pass
		genres = [
			('Action', 'action', True, '28'), ('Adventure', 'adventure', True, '12'), ('Animation', 'animation', True, '16'),
			('Biography', 'biography', True), ('Comedy', 'comedy', True, '35'), ('Crime', 'crime', True, '80'),
			('Documentary', 'documentary', True, '99'), ('Drama', 'drama', True, '18'), ('Family', 'family', True, '10751'),
			('Fantasy', 'fantasy', True, '14'), ('Film-Noir', 'film-noir', True), ('History', 'history', True, '36'),
			('Horror', 'horror', True, '27'), ('Music', 'music', True, '10402'), ('Musical', 'musical', True),
			('Mystery', 'mystery', True, '9648'), ('Romance', 'romance', True, '10749'), ('Science Fiction', 'sci-fi', True, '878'),
			('Sport', 'sport', True), ('Thriller', 'thriller', True, '53'), ('War', 'war', True, '10752'), ('Western', 'western', True, '37')]
		for i in genres:
			if self.imdb_link in url: self.list.append({'content': 'genres', 'name': cleangenre.lang(i[0], self.lang), 'url': url % i[1] if i[2] else self.keyword_link % i[1], 'image': i[0] + '.jpg', 'icon': i[0] + '.png', 'action': 'movies'})
			if self.tmdb_link in url:
				try: self.list.append({'content': 'genres', 'name': cleangenre.lang(i[0], self.lang), 'url': url % ('%s', i[3]), 'image': i[0] + '.jpg', 'icon': i[0] + '.png', 'action': 'tmdbmovies'})
				except: pass
		self.addDirectory(self.list)
		return self.list

	def languages(self):
		languages = [('Arabic', 'ar'), ('Bosnian', 'bs'), ('Bulgarian', 'bg'), ('Chinese', 'zh'), ('Croatian', 'hr'), ('Dutch', 'nl'),
			('English', 'en'), ('Finnish', 'fi'), ('French', 'fr'), ('German', 'de'), ('Greek', 'el'),('Hebrew', 'he'), ('Hindi ', 'hi'),
			('Hungarian', 'hu'), ('Icelandic', 'is'), ('Italian', 'it'), ('Japanese', 'ja'), ('Korean', 'ko'), ('Macedonian', 'mk'),
			('Norwegian', 'no'), ('Persian', 'fa'), ('Polish', 'pl'), ('Portuguese', 'pt'), ('Punjabi', 'pa'), ('Romanian', 'ro'),
			('Russian', 'ru'), ('Serbian', 'sr'), ('Slovenian', 'sl'), ('Spanish', 'es'), ('Swedish', 'sv'), ('Turkish', 'tr'), ('Ukrainian', 'uk')]
		for i in languages:
			self.list.append({'content': 'countries', 'name': str(i[0]), 'url': self.language_link % i[1], 'image': 'languages.png', 'icon': 'DefaultAddonLanguage.png', 'action': 'movies'})
		self.addDirectory(self.list)
		return self.list

	def certifications(self, url):
		try: url = getattr(self, url + '_link')
		except: pass
		certificates = [
			('General Audience (G)', 'US%3AG', 'G'),
			('Parental Guidance (PG)', 'US%3APG', 'PG'),
			('Parental Caution (PG-13)', 'US%3APG-13', 'PG-13'),
			('Parental Restriction (R)', 'US%3AR', 'R'),
			('Mature Audience (NC-17)', 'US%3ANC-17', 'NC-17')]
		for i in certificates:
			if self.imdb_link in url: self.list.append({'content': 'tags', 'name': str(i[0]), 'url': url % i[1], 'image': 'certificates.png', 'icon': 'certificates.png', 'action': 'movies'})
			if self.tmdb_link in url: self.list.append({'content': 'tags', 'name': str(i[0]), 'url': url % ('%s', i[2]), 'image': 'certificates.png', 'icon': 'certificates.png', 'action': 'tmdbmovies'})
		self.addDirectory(self.list)
		return self.list

	def years(self, url):
		try: url = getattr(self, url + '_link')
		except: pass
		year = (self.date_time.strftime('%Y'))
		for i in range(int(year)-0, 1900, -1):
			if self.imdb_link in url: self.list.append({'content': 'years', 'name': str(i), 'url': url % (str(i), str(i)), 'image': 'years.png', 'icon': 'DefaultYear.png', 'action': 'movies'})
			if self.tmdb_link in url: self.list.append({'content': 'years', 'name': str(i), 'url': url % ('%s', str(i)), 'image': 'years.png', 'icon': 'DefaultYear.png', 'action': 'tmdbmovies'})
		self.addDirectory(self.list)
		return self.list

	def moviesListToLibrary(self, url):
		url = getattr(self, url + '_link')
		u = urlparse(url).netloc.lower()
		try:
			control.hide()
			# if u in self.tmdb_link: items = tmdb_indexer.TMDb().userlists(url)
			if u in self.tmdb_link: items = tmdb_indexer().userlists(url)
			elif u in self.trakt_link:
				if url in self.traktlikedlists_link:
					items = self.traktLlikedlists()
				else: items = self.trakt_user_lists(url, self.trakt_user)
			items = [(i['name'], i['url']) for i in items]
			message = 32663
			if 'themoviedb' in url: message = 32681
			select = control.selectDialog([i[0] for i in items], getLS(message))
			list_name = items[select][0]
			if select == -1: return
			link = items[select][1]
			link = link.split('&sort_by')[0]
			link = link.split('?limit=')[0]
			from resources.lib.modules import library
			library.libmovies().range(link, list_name)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def userlists(self):
		userlists = []
		try:
			if not self.traktCredentials: raise Exception()
			activity = trakt.getActivity()
			self.list = [] ; lists = []
			try:
				if activity > cache.timeout(self.trakt_user_lists, self.traktlists_link, self.trakt_user): raise Exception()
				lists += cache.get(self.trakt_user_lists, 720, self.traktlists_link, self.trakt_user)
			except:
				lists += cache.get(self.trakt_user_lists, 0, self.traktlists_link, self.trakt_user)
			userlists += lists
		except: pass
		try:
			if not self.imdb_user: raise Exception()
			self.list = []
			lists = cache.get(self.imdb_user_list, 0, self.imdblists_link)
			userlists += lists
		except: pass
		try:
			if self.tmdb_session_id == '': raise Exception()
			self.list = []
			url = self.tmdb_link + '/3/account/{account_id}/lists?api_key=%s&language=en-US&session_id=%s&page=1' % ('%s', self.tmdb_session_id)
			# lists = cache.get(tmdb_indexer.TMDb().userlists, 0, url)
			lists = cache.get(tmdb_indexer().userlists, 0, url)
			for i in range(len(lists)): lists[i].update({'image': 'tmdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'tmdbmovies'})
			userlists += lists
		except: pass
		self.list = []
		for i in range(len(userlists)): # Filter the user's own lists that were
			contains = False
			adapted = userlists[i]['url'].replace('/me/', '/%s/' % self.trakt_user)
			for j in range(len(self.list)):
				if adapted == self.list[j]['url'].replace('/me/', '/%s/' % self.trakt_user):
					contains = True
					break
			if not contains: self.list.append(userlists[i])
		if self.tmdb_session_id != '': # TMDb Favorites
			url = self.tmdb_link + '/3/account/{account_id}/favorite/movies?api_key=%s&session_id=%s&sort_by=created_at.asc&page=1' % ('%s', self.tmdb_session_id) 
			self.list.insert(0, {'name': getLS(32026), 'url': url, 'image': 'tmdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'tmdbmovies'})
		if self.tmdb_session_id != '': # TMDb Watchlist
			url = self.tmdb_link + '/3/account/{account_id}/watchlist/movies?api_key=%s&session_id=%s&sort_by=created_at.asc&page=1' % ('%s', self.tmdb_session_id)
			self.list.insert(0, {'name': getLS(32033), 'url': url, 'image': 'tmdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'tmdbmovies'})
		if self.imdb_user != '': # imdb Watchlist
			self.list.insert(0, {'name': getLS(32033), 'url': self.imdbwatchlist_link, 'image': 'imdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'movies'})
		if self.imdb_user != '': # imdb My Ratings
			self.list.insert(0, {'name': getLS(32025), 'url': self.imdbratings_link, 'image': 'imdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'movies'})
		self.addDirectory(self.list, queue=True)
		return self.list

	def traktCollection(self, url, create_directory=True):
		self.list = []
		try:
			q = dict(parse_qsl(urlsplit(url).query))
			index = int(q['page']) - 1
			self.list = traktsync.fetch_collection('movies_collection')
			self.sort() # sort before local pagination
			if getSetting('trakt.paginate.lists') == 'true' and self.list:
				paginated_ids = [self.list[x:x + int(self.page_limit)] for x in range(0, len(self.list), int(self.page_limit))]
				self.list = paginated_ids[index]
			try:
				if int(q['limit']) != len(self.list): raise Exception()
				q.update({'page': str(int(q['page']) + 1)})
				q = (urlencode(q)).replace('%2C', ',')
				next = url.replace('?' + urlparse(url).query, '') + '?' + q
			except: next = ''
			for i in range(len(self.list)): self.list[i]['next'] = next
			self.worker()
			if self.list is None: self.list = []
			if create_directory: self.movieDirectory(self.list)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def traktWatchlist(self, url, create_directory=True):
		self.list = []
		try:
			q = dict(parse_qsl(urlsplit(url).query))
			index = int(q['page']) - 1
			self.list = traktsync.fetch_watch_list('movies_watchlist')
			self.sort(type='movies.watchlist') # sort before local pagination
			if getSetting('trakt.paginate.lists') == 'true' and self.list:
				paginated_ids = [self.list[x:x + int(self.page_limit)] for x in range(0, len(self.list), int(self.page_limit))]
				self.list = paginated_ids[index]
			try:
				if int(q['limit']) != len(self.list): raise Exception()
				q.update({'page': str(int(q['page']) + 1)})
				q = (urlencode(q)).replace('%2C', ',')
				next = url.replace('?' + urlparse(url).query, '') + '?' + q
			except: next = ''
			for i in range(len(self.list)): self.list[i]['next'] = next
			self.worker()
			if self.list is None: self.list = []
			if create_directory: self.movieDirectory(self.list)
			return self.list
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def traktLlikedlists(self):
		items = traktsync.fetch_liked_list('', True)
		for item in items:
			try:
				if item['content_type'] == 'shows': continue
				list_name = item['list_name']
				list_owner = item['list_owner']
				list_owner_slug = item['list_owner_slug']
				list_id = item['trakt_id']
				list_url = self.traktlist_link % (list_owner_slug, list_id)
				next = ''
				label = '%s - [COLOR %s]%s[/COLOR]' % (list_name, self.highlight_color, list_owner)
				self.list.append({'name': label, 'list_type': 'traktPulicList', 'url': list_url, 'list_owner': list_owner, 'list_name': list_name, 'list_id': list_id, 'context': list_url, 'next': next, 'image': 'trakt.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'movies'})
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		self.list = sorted(self.list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['name'].lower()))
		self.addDirectory(self.list, queue=True)
		return self.list

	def trakt_list(self, url, user):
		self.list = []
		if ',return' in url: url = url.split(',return')[0]
		items = trakt.getTraktAsJson(url)
		if not items: return
		try:
			q = dict(parse_qsl(urlsplit(url).query))
			if int(q['limit']) != len(items): raise Exception()
			q.update({'page': str(int(q['page']) + 1)})
			q = (urlencode(q)).replace('%2C', ',')
			next = url.replace('?' + urlparse(url).query, '') + '?' + q
		except: next = ''
		for item in items: # rating and votes via TMDb, or I must use "extended=full" and it slows down
			try:
				values = {}
				values['next'] = next 
				values['added'] = item.get('listed_at', '')
				values['paused_at'] = item.get('paused_at', '') # for unfinished
				try: values['progress'] = item['progress']
				except: values['progress'] = ''
				try: values['lastplayed'] = item['watched_at'] # for history
				except: values['lastplayed'] = ''
				movie = item.get('movie') or item
				values['title'] = movie.get('title')
				values['originaltitle'] = values['title']
				values['year'] = str(movie.get('year', '')) if movie.get('year') else ''
				ids = movie.get('ids', {})
				values['imdb'] = str(ids.get('imdb', '')) if ids.get('imdb') else ''
				values['tmdb'] = str(ids.get('tmdb', '')) if ids.get('tmdb') else ''
				values['tvdb'] = ''
				self.list.append(values)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return self.list

	def trakt_userList(self, url, create_directory=True):
		self.list = []
		q = dict(parse_qsl(urlsplit(url).query))
		index = int(q['page']) - 1
		def userList_totalItems(url):
			items = trakt.getTraktAsJson(url)
			if not items: return
			for item in items:
				try:
					values = {}
					values['added'] = item.get('listed_at', '')
					movie = item['movie']
					values['title'] = movie.get('title')
					values['originaltitle'] = values['title']
					try: values['premiered'] = movie.get('released', '')[:10]
					except: values['premiered'] = ''
					values['year'] = str(movie.get('year', '')) if movie.get('year') else ''
					if not values['year']:
						try: values['year'] = str(values['premiered'][:4])
						except: values['year'] = ''
					ids = movie.get('ids', {})
					values['imdb'] = str(ids.get('imdb', '')) if ids.get('imdb') else ''
					values['tmdb'] = str(ids.get('tmdb', '')) if ids.get('tmdb') else ''
					values['rating'] = movie.get('rating')
					values['votes'] = movie.get('votes')
					self.list.append(values)
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
			return self.list
		self.list = cache.get(userList_totalItems, 48, url.split('limit')[0] + 'extended=full')
		if not self.list: return
		self.sort() # sort before local pagination
		total_pages = 1
		if getSetting('trakt.paginate.lists') == 'true':
			paginated_ids = [self.list[x:x + int(self.page_limit)] for x in range(0, len(self.list), int(self.page_limit))]
			total_pages = len(paginated_ids)
			self.list = paginated_ids[index]
		try:
			if int(q['limit']) != len(self.list): raise Exception()
			if int(q['page']) == total_pages: raise Exception()
			q.update({'page': str(int(q['page']) + 1)})
			q = (urlencode(q)).replace('%2C', ',')
			next = url.replace('?' + urlparse(url).query, '') + '?' + q
		except: next = ''
		for i in range(len(self.list)): self.list[i]['next'] = next
		self.worker()
		if self.list is None: self.list = []
		if create_directory: self.movieDirectory(self.list)
		return self.list

	def trakt_user_lists(self, url, user):
		items = traktsync.fetch_user_lists('', True)
		for item in items:
			try:
				if item['content_type'] == 'shows': continue
				list_name = item['list_name']
				list_owner = item['list_owner']
				list_owner_slug = item['list_owner_slug']
				list_id = item['trakt_id']
				list_url = self.traktlist_link % (list_owner_slug, list_id)
				next = ''
				label = '%s - [COLOR %s]%s[/COLOR]' % (list_name, self.highlight_color, list_owner)
				self.list.append({'name': label, 'url': list_url, 'list_owner': list_owner, 'list_name': list_name, 'list_id': list_id, 'context': list_url, 'next': next, 'image': 'trakt.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'movies'})
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		self.list = sorted(self.list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['name'].lower()))
		return self.list

	def trakt_public_list(self, url):
		try:
			items = trakt.getTrakt(url).json()
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		try:
			q = dict(parse_qsl(urlsplit(url).query))
			if int(q['limit']) != len(items): raise Exception()
			q.update({'page': str(int(q['page']) + 1)})
			q = (urlencode(q)).replace('%2C', ',')
			next = url.replace('?' + urlparse(url).query, '') + '?' + q
		except: next = ''

		for item in items:
			try:
				if item.get('type', '') == 'officiallist': continue #seems bugy so until Justin replies hold off
				list_item = item.get('list', {})
				list_name = list_item.get('name', '')
				list_id = list_item.get('ids', {}).get('trakt', '')
				list_owner = list_item.get('user', {}).get('username', '')
				list_owner_slug = list_item.get('user', {}).get('ids', {}).get('slug', '')
				if any(list_item.get('privacy', '') == value for value in ('private', 'friends')): continue
				list_url = self.traktlist_link % (list_owner_slug, list_id)
				list_content = traktsync.fetch_public_list(list_id)
				if not list_content: pass
				else: 
					if list_content.get('content_type', '') == 'shows': continue
				label = '%s - [COLOR %s]%s[/COLOR]' % (list_name, self.highlight_color, list_owner)
				self.list.append({'name': label, 'list_type': 'traktPulicList', 'url': list_url, 'list_owner': list_owner, 'list_name': list_name, 'list_id': list_id, 'context': list_url, 'next': next, 'image': 'trakt.png', 'icon': 'trakt.png', 'action': 'movies'})
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return self.list

	def imdb_list(self, url, comingSoon=False, isRatinglink=False):
		list = []
		try:
			for i in re.findall(r'date\[(\d+)\]', url):
				url = url.replace('date[%s]' % i, (self.date_time - timedelta(days=int(i))).strftime('%Y-%m-%d'))
			def imdb_watchlist_id(url):
				return client.parseDOM(client.request(url), 'meta', ret='content', attrs = {'property': 'pageId'})[0]
			if url == self.imdbwatchlist_link:
				url = cache.get(imdb_watchlist_id, 8640, url)
				url = self.imdbwatchlist2_link % url
			result = client.request(url).replace('\n', ' ')
			items = client.parseDOM(result, 'div', attrs = {'class': '.+? lister-item'}) + client.parseDOM(result, 'div', attrs = {'class': 'lister-item .+?'})
			items += client.parseDOM(result, 'div', attrs = {'class': 'list_item.+?'})
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
			return

		next = ''
		try:
			# HTML syntax error, " directly followed by attribute name. Insert space in between. parseDOM can otherwise not handle it.
			result = result.replace('"class="lister-page-next', '" class="lister-page-next')
			next = client.parseDOM(result, 'a', ret='href', attrs = {'class': '.*?lister-page-next.*?'})
			if len(next) == 0:
				next = client.parseDOM(result, 'div', attrs = {'class': 'pagination'})[0]
				next = zip(client.parseDOM(next, 'a', ret='href'), client.parseDOM(next, 'a'))
				next = [i[0] for i in next if 'Next' in i[1]]
			next = url.replace(urlparse(url).query, urlparse(next[0]).query)
			next = client.replaceHTMLCodes(next)
		except: next = ''
		if not next:
			try:
				next = client.parseDOM(result, 'div', attrs = {'class': 'see-more'})
				next = client.parseDOM(next, 'a', ret='href')[1]
				next = self.imdb_link + next
			except: next = ''

		for item in items:
			try:
				main_title = client.replaceHTMLCodes(client.parseDOM(item, 'a')[1])
				title = main_title.split(' (')[0]
				year = client.parseDOM(item, 'span', attrs = {'class': 'lister-item-year.+?'})
				if not year: year = [main_title]
				try: year = re.findall(r'(\d{4})', year[0])[0]
				except: continue
				if not comingSoon:
					if int(year) > int((self.date_time).strftime('%Y')): continue
				imdb = client.parseDOM(item, 'a', ret='href')[0]
				imdb = re.findall(r'(tt\d*)', imdb)[0]
				try: show = '–'.decode('utf-8') in str(year).decode('utf-8') or '-'.decode('utf-8') in str(year).decode('utf-8') # check with Matrix
				except: show = False
				if show or ('Episode:' in item): raise Exception() # Some lists contain TV shows.
				rating = votes = ''
				try:
					rating = client.parseDOM(item, 'div', attrs = {'class': 'ratings-bar'})
					rating = client.parseDOM(rating, 'strong')[0]
				except:
					try:
						rating = client.parseDOM(item, 'span', attrs = {'class': 'rating-rating'})
						rating = client.parseDOM(rating, 'span', attrs = {'class': 'value'})[0]
					except:
						try: rating = client.parseDOM(item, 'div', ret='data-value', attrs = {'class': '.*?imdb-rating'})[0] 
						except:
							try: rating = client.parseDOM(item, 'span', attrs = {'class': 'ipl-rating-star__rating'})[0]
							except: rating = ''
				try: votes = client.parseDOM(item, 'span', attrs = {'name': 'nv'})[0]
				except:
					try: votes = client.parseDOM(item, 'div', ret='title', attrs = {'class': '.*?rating-list'})[0]
					except:
						try: votes = re.findall(r'\((.+?) vote(?:s|)\)', votes)[0]
						except: votes = ''
				list.append({'title': title, 'originaltitle': title, 'year': year, 'imdb': imdb, 'tmdb': '', 'tvdb': '', 'rating': rating, 'votes': votes, 'next': next}) # just let super_info() TMDb request provide the meta and pass min to retrieve it
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return list

	def imdb_person_list(self, url):
		self.list = []
		try:
			result = client.request(url)
			items = client.parseDOM(result, 'div', attrs = {'class': '.+?etail'})
		except: return
		for item in items:
			try:
				name = client.parseDOM(item, 'img', ret='alt')[0]
				url = client.parseDOM(item, 'a', ret='href')[0]
				url = re.findall(r'(nm\d*)', url, re.I)[0]
				url = self.person_link % url
				url = client.replaceHTMLCodes(url)
				image = client.parseDOM(item, 'img', ret='src')[0]
				image = re.sub(r'(?:_SX|_SY|_UX|_UY|_CR|_AL)(?:\d+|_).+?\.', '_SX500.', image)
				image = client.replaceHTMLCodes(image)
				self.list.append({'name': name, 'url': url, 'image': image})
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		return self.list

	def imdb_user_list(self, url):
		list = []
		try:
			result = client.request(url)
			items = client.parseDOM(result, 'li', attrs={'class': 'ipl-zebra-list__item user-list'})
		except:
			from resources.lib.modules import log_utils
			log_utils.error()
		for item in items:
			try:
				name = client.parseDOM(item, 'a')[0]
				name = client.replaceHTMLCodes(name)
				url = client.parseDOM(item, 'a', ret='href')[0]
				url = url.split('/list/', 1)[-1].strip('/')
				url = self.imdblist_link % url
				url = client.replaceHTMLCodes(url)
				list.append({'name': name, 'url': url, 'context': url, 'image': 'imdb.png', 'icon': 'DefaultVideoPlaylists.png', 'action': 'movies'})
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		list = sorted(list, key=lambda k: re.sub(r'(^the |^a |^an )', '', k['name'].lower()))
		return list

	def worker(self):
		try:
			if not self.list: return
			self.meta = []
			total = len(self.list)
			for i in range(0, total): self.list[i].update({'metacache': False})
			self.list = metacache.fetch(self.list, self.lang, self.user)
			for r in range(0, total, 40):
				threads = []
				append = threads.append
				for i in range(r, r + 40):
					if i < total: append(Thread(target=self.super_info, args=(i,)))
				[i.start() for i in threads]
				[i.join() for i in threads]
			if self.meta: metacache.insert(self.meta)
			self.list = [i for i in self.list if i.get('tmdb')]
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def super_info(self, i):
		try:
			if self.list[i]['metacache']: return
			imdb, tmdb = self.list[i].get('imdb', ''), self.list[i].get('tmdb', '')
#### -- Missing id's lookup -- ####
			if not tmdb and imdb:
				try:
					# result = cache.get(tmdb_indexer.Movies().IdLookup, 96, imdb)
					result = cache.get(tmdb_indexer().IdLookup, 96, imdb)
					tmdb = str(result.get('id', '')) if result.get('id') else ''
				except: tmdb = ''
			if not tmdb and imdb:
				trakt_ids = trakt.IdLookup('imdb', imdb, 'movie') # "trakt.IDLookup()" caches item
				if trakt_ids: tmdb = str(trakt_ids.get('tmdb', '')) if trakt_ids.get('tmdb') else ''
			if not tmdb and not imdb:
				try:
					results = trakt.SearchMovie(title=quote_plus(self.list[i]['title']), year=self.list[i]['year'], fields='title', full=False) # "trakt.SearchMovie()" caches item
					if results[0]['movie']['title'] != self.list[i]['title'] or results[0]['movie']['year'] != self.list[i]['year']: return
					ids = results[0].get('movie', {}).get('ids', {})
					if not tmdb: tmdb = str(ids.get('tmdb', '')) if ids.get('tmdb') else ''
					if not imdb: imdb = str(ids.get('imdb', '')) if ids.get('imdb') else ''
				except: pass
#################################
			if not tmdb: return
			# movie_meta = tmdb_indexer.Movies().get_movie_meta(tmdb)
			movie_meta = tmdb_indexer().get_movie_meta(tmdb)
			if not movie_meta or '404:NOT FOUND' in movie_meta: return # trakt search turns up alot of junk with wrong tmdb_id's causing 404's
			values = {}
			values.update(movie_meta)
			if 'rating' in self.list[i] and self.list[i]['rating']: values['rating'] = self.list[i]['rating'] # prefer imdb,trakt rating and votes if set
			if 'votes' in self.list[i] and self.list[i]['votes']: values['votes'] = self.list[i]['votes']
			if 'year' in self.list[i] and self.list[i]['year'] != values.get('year'): values['year'] = self.list[i]['year']
			if not imdb: imdb = values.get('imdb', '')
			if not values.get('imdb'): values['imdb'] = imdb
			if not values.get('tmdb'): values['tmdb'] = tmdb
			if self.lang != 'en':
				try:
					if 'available_translations' in self.list[i] and self.lang not in self.list[i]['available_translations']: raise Exception()
					trans_item = trakt.getMovieTranslation(imdb, self.lang, full=True)
					if trans_item:
						if trans_item.get('title'): values['title'] = trans_item.get('title')
						if trans_item.get('overview'): values['plot'] =trans_item.get('overview')
				except:
					from resources.lib.modules import log_utils
					log_utils.error()
			if self.enable_fanarttv:
				extended_art = fanarttv_cache.get(FanartTv().get_movie_art, 336, imdb, tmdb)
				if extended_art: values.update(extended_art)
			values = dict((k, v) for k, v in iter(values.items()) if v is not None and v != '') # remove empty keys so .update() doesn't over-write good meta with empty values.
			self.list[i].update(values)
			meta = {'imdb': imdb, 'tmdb': tmdb, 'tvdb': '', 'lang': self.lang, 'user': self.user, 'item': values}
			self.meta.append(meta)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

	def movieDirectory(self, items, unfinished=False, next=True):
		from sys import argv # some functions like ActivateWindow() throw invalid handle less this is imported here.
		if not items: # with reuselanguageinvoker on an empty directory must be loaded, do not use sys.exit()
			control.hide() ; control.notification(title=32001, message=33049)
		from resources.lib.modules.player import Bookmarks
		sysaddon, syshandle = 'plugin://plugin.video.venom/', int(argv[1])
		play_mode = getSetting('play.mode')
		rescrape_useDefault = getSetting('rescrape.default') == 'true'
		rescrape_method = getSetting('rescrape.default2')
		is_widget = 'plugin' not in control.infoLabel('Container.PluginName')
		settingFanart = getSetting('fanart') == 'true'
		addonPoster, addonFanart, addonBanner = control.addonPoster(), control.addonFanart(), control.addonBanner()
		indicators = getMovieIndicators() # refresh not needed now due to service sync
		if play_mode == '1': playbackMenu = getLS(32063)
		else: playbackMenu = getLS(32064)
		if trakt.getTraktIndicatorsInfo(): watchedMenu, unwatchedMenu = getLS(32068), getLS(32069)
		else: watchedMenu, unwatchedMenu = getLS(32066), getLS(32067)
		playlistManagerMenu, queueMenu = getLS(35522), getLS(32065)
		traktManagerMenu, addToLibrary = getLS(32070), getLS(32551)
		nextMenu, clearSourcesMenu = getLS(32053), getLS(32611)
		rescrapeMenu, findSimilarMenu = getLS(32185), getLS(32184)
		for i in items:
			try:
				imdb, tmdb, title, year = i.get('imdb', ''), i.get('tmdb', ''), i['title'], i.get('year', '')
				trailer, runtime = i.get('trailer'), i.get('duration')
				label = '%s (%s)' % (title, year)
				try: labelProgress = label + '[COLOR %s]  [%s][/COLOR]' % (self.highlight_color, str(round(float(i['progress']), 1)) + '%')
				except: labelProgress = label
				try:
					if int(re.sub(r'[^0-9]', '', str(i['premiered']))) > int(re.sub(r'[^0-9]', '', str(self.today_date))): 
						labelProgress = '[COLOR %s][I]%s[/I][/COLOR]' % (self.unairedcolor, labelProgress)
				except: pass
				if i.get('traktHistory') is True: # uses Trakt lastplayed
					try:
						air_datetime = tools.convert_time(stringTime=i.get('lastplayed', ''), zoneFrom='utc', zoneTo='local', formatInput='%Y-%m-%dT%H:%M:%S.000Z', formatOutput='%b %d %Y %I:%M %p', remove_zeroes=True)
						labelProgress = labelProgress + '[COLOR %s]  [%s][/COLOR]' % (self.highlight_color, air_datetime)
					except: pass
				sysname, systitle = quote_plus(label), quote_plus(title)
				meta = dict((k, v) for k, v in iter(i.items()) if v is not None and v != '')
				meta.update({'code': imdb, 'imdbnumber': imdb, 'mediatype': 'movie', 'tag': [imdb, tmdb]})
				try: meta.update({'genre': cleangenre.lang(meta['genre'], self.lang)})
				except: pass

				if self.prefer_tmdbArt: poster = meta.get('poster3') or meta.get('poster') or meta.get('poster2') or addonPoster
				else: poster = meta.get('poster2') or meta.get('poster3') or meta.get('poster') or addonPoster
				fanart = ''
				if settingFanart:
					if self.prefer_tmdbArt: fanart = meta.get('fanart3') or meta.get('fanart') or meta.get('fanart2') or addonFanart
					else: fanart = meta.get('fanart2') or meta.get('fanart3') or meta.get('fanart') or addonFanart
				landscape = meta.get('landscape') or fanart
				thumb = meta.get('thumb') or poster or landscape
				icon = meta.get('icon') or poster
				banner = meta.get('banner3') or meta.get('banner2') or meta.get('banner') or addonBanner
				art = {}
				art.update({'icon': icon, 'thumb': thumb, 'banner': banner, 'poster': poster, 'fanart': fanart, 'landscape': landscape, 'clearlogo': meta.get('clearlogo', ''),
								'clearart': meta.get('clearart', ''), 'discart': meta.get('discart', ''), 'keyart': meta.get('keyart', '')})
				for k in ('metacache', 'poster2', 'poster3', 'fanart2', 'fanart3', 'banner2', 'banner3', 'trailer'): meta.pop(k, None)
				meta.update({'poster': poster, 'fanart': fanart, 'banner': banner})
				sysmeta, sysart = quote_plus(jsdumps(meta)), quote_plus(jsdumps(art))
				url = '%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)
				sysurl = quote_plus(url)
####-Context Menu and Overlays-####
				cm = []
				try:
					watched = getMovieOverlay(indicators, imdb) == '5'
					if self.traktCredentials:
						cm.append((traktManagerMenu, 'RunPlugin(%s?action=tools_traktManager&name=%s&imdb=%s&watched=%s&unfinished=%s)' % (sysaddon, sysname, imdb, watched, unfinished)))
					if watched:
						cm.append((unwatchedMenu, 'RunPlugin(%s?action=playcount_Movie&name=%s&imdb=%s&query=4)' % (sysaddon, sysname, imdb)))
						meta.update({'playcount': 1, 'overlay': 5})
						# meta.update({'lastplayed': trakt.watchedMoviesTime(imdb)}) # no skin support
					else:
						cm.append((watchedMenu, 'RunPlugin(%s?action=playcount_Movie&name=%s&imdb=%s&query=5)' % (sysaddon, sysname, imdb)))
						meta.update({'playcount': 0, 'overlay': 4})
				except: pass
				cm.append((playlistManagerMenu, 'RunPlugin(%s?action=playlist_Manager&name=%s&url=%s&meta=%s&art=%s)' % (sysaddon, sysname, sysurl, sysmeta, sysart)))
				cm.append((queueMenu, 'RunPlugin(%s?action=playlist_QueueItem&name=%s)' % (sysaddon, sysname)))
				cm.append((addToLibrary, 'RunPlugin(%s?action=library_movieToLibrary&name=%s&title=%s&year=%s&imdb=%s&tmdb=%s)' % (sysaddon, sysname, systitle, year, imdb, tmdb)))
				cm.append((findSimilarMenu, 'Container.Update(%s?action=movies&url=%s)' % (sysaddon, quote_plus('https://api.trakt.tv/movies/%s/related?limit=20&page=1,return' % imdb))))
				if i.get('belongs_to_collection', ''):
					cm.append(('Browse Collection', 'Container.Update(%s?action=collections&url=%s)' % (
							sysaddon, quote_plus('https://api.themoviedb.org/3/collection/%s?api_key=%s&page=1,return' % (i['belongs_to_collection']['id'], self.tmdb_key)))))
				cm.append((playbackMenu, 'RunPlugin(%s?action=alterSources&url=%s&meta=%s)' % (sysaddon, sysurl, sysmeta)))
				if not rescrape_useDefault:
					cm.append(('Rescrape Options ------>', 'PlayMedia(%s?action=rescrapeMenu&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
				else:
					if rescrape_method == '0':
						cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&rescrape=true&select=1)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
					if rescrape_method == '1':
						cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&rescrape=true&select=0)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
					if rescrape_method == '2':
						cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&rescrape=true&all_providers=true&select=1)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
					if rescrape_method == '3':
						cm.append((rescrapeMenu, 'PlayMedia(%s?action=play_Item&title=%s&year=%s&imdb=%s&tmdb=%s&meta=%s&rescrape=true&all_providers=true&select=0)' % (sysaddon, systitle, year, imdb, tmdb, sysmeta)))
				cm.append((clearSourcesMenu, 'RunPlugin(%s?action=cache_clearSources)' % sysaddon))
				cm.append(('[COLOR red]Venom Settings[/COLOR]', 'RunPlugin(%s?action=tools_openSettings)' % sysaddon))
####################################
				if trailer: meta.update({'trailer': trailer}) # removed temp so it's not passed to CM items, only infoLabels for skin
				else: meta.update({'trailer': '%s?action=play_Trailer&type=%s&name=%s&year=%s&imdb=%s' % (sysaddon, 'movie', sysname, year, imdb)})
				item = control.item(label=labelProgress, offscreen=True)
				if 'castandart' in i: item.setCast(i['castandart'])
				item.setArt(art)
				item.setUniqueIDs({'imdb': imdb, 'tmdb': tmdb})
				item.setProperty('IsPlayable', 'true')
				if is_widget: item.setProperty('isVenom_widget', 'true')
				if self.unairedcolor not in labelProgress:
					resumetime = Bookmarks().get(name=label, imdb=imdb, tmdb=tmdb, year=str(year), runtime=runtime, ck=True)
					# item.setProperty('TotalTime', str(meta['duration'])) # Adding this property causes the Kodi bookmark CM items to be added
					item.setProperty('ResumeTime', str(resumetime))
					try:
						watched_percent = round(float(resumetime) / float(runtime) * 100, 1) # resumetime and runtime are both in seconds
						item.setProperty('PercentPlayed', str(watched_percent))
					except: pass

				item.setInfo(type='video', infoLabels=control.metadataClean(meta))
				item.addContextMenuItems(cm)
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=False)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		if next:
			try:
				if not items: raise Exception()
				url = items[0]['next']
				if not url: raise Exception()
				url_params = dict(parse_qsl(urlsplit(url).query))
				if 'imdb.com' in url and 'start' in url_params: page = '  [I](%s)[/I]' % str(int(((int(url_params.get('start')) - 1) / int(self.page_limit)) + 1))
				elif 'www.imdb.com/movies-coming-soon/' in url: page = '  [I](%s)[/I]' % re.search(r'(\d{4}-\d{2})', url).group(1)
				else: page = '  [I](%s)[/I]' % url_params.get('page')
				if 'None' in page: page = page.split('  [I]')[0]
				nextMenu = '[COLOR skyblue]' + nextMenu + page + '[/COLOR]'
				u = urlparse(url).netloc.lower()
				if u not in self.tmdb_link: url = '%s?action=moviePage&url=%s' % (sysaddon, quote_plus(url))
				elif u in self.tmdb_link: url = '%s?action=tmdbmoviePage&url=%s' % (sysaddon, quote_plus(url))
				item = control.item(label=nextMenu, offscreen=True)
				icon = control.addonNext()
				item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon})
				item.setProperty ('SpecialSort', 'bottom')
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		control.content(syshandle, 'movies')
		control.directory(syshandle, cacheToDisc=True)
		control.sleep(100)
		views.setView('movies', {'skin.estuary': 55, 'skin.confluence': 500})

	def addDirectory(self, items, queue=False):
		from sys import argv # some functions like ActivateWindow() throw invalid handle less this is imported here.
		if not items: # with reuselanguageinvoker on an empty directory must be loaded, do not use sys.exit()
			content = '' ; control.hide() ; control.notification(title=32001, message=33049)
		sysaddon, syshandle = 'plugin://plugin.video.venom/', int(argv[1])
		addonThumb = control.addonThumb()
		artPath = control.artPath()
		queueMenu, playRandom, addToLibrary = getLS(32065), getLS(32535), getLS(32551)
		likeMenu, unlikeMenu = getLS(32186), getLS(32187)
		for i in items:
			try:
				content = i.get('content', '')
				name = i['name']
				if i['image'].startswith('http'): poster = i['image']
				elif artPath: poster = control.joinPath(artPath, i['image'])
				else: poster = addonThumb
				if content == 'genres':
					icon = control.joinPath(control.genreIconPath(), i['icon']) or 'DefaultFolder.png'
					poster = control.joinPath(control.genrePosterPath(), i['image']) or addonThumb
				else:
					icon = i['icon']
					if icon.startswith('http'): pass
					elif not icon.startswith('Default'): icon = control.joinPath(artPath, icon)
				url = '%s?action=%s' % (sysaddon, i['action'])
				try: url += '&url=%s' % quote_plus(i['url'])
				except: pass
				cm = []
				if (i.get('list_type', '') == 'traktPulicList') and self.traktCredentials:
					liked = traktsync.fetch_liked_list(i['list_id'])
					if not liked:
						cm.append((likeMenu, 'RunPlugin(%s?action=tools_likeList&list_owner=%s&list_name=%s&list_id=%s)' % (sysaddon, quote_plus(i['list_owner']), quote_plus(i['list_name']), i['list_id'])))
					else:
						name = '[COLOR %s][Liked][/COLOR] %s' % (self.highlight_color, name)
						cm.append((unlikeMenu, 'RunPlugin(%s?action=tools_unlikeList&list_owner=%s&list_name=%s&list_id=%s)' % (sysaddon, quote_plus(i['list_owner']), quote_plus(i['list_name']), i['list_id'])))
				cm.append((playRandom, 'RunPlugin(%s?action=play_Random&rtype=movie&url=%s)' % (sysaddon, quote_plus(i['url']))))
				if queue: cm.append((queueMenu, 'RunPlugin(%s?action=playlist_QueueItem)' % sysaddon))
				try:
					if getSetting('library.service.update') == 'true':
						cm.append((addToLibrary, 'RunPlugin(%s?action=library_moviesToLibrary&url=%s&name=%s)' % (sysaddon, quote_plus(i['context']), name)))
				except: pass
				cm.append(('[COLOR red]Venom Settings[/COLOR]', 'RunPlugin(%s?action=tools_openSettings)' % sysaddon))
				item = control.item(label=name, offscreen=True)
				item.setArt({'icon': icon, 'poster': poster, 'thumb': poster, 'fanart': control.addonFanart(), 'banner': poster})
				item.setInfo(type='video', infoLabels={'plot': name})
				item.addContextMenuItems(cm)
				control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
			except:
				from resources.lib.modules import log_utils
				log_utils.error()
		try:
			if not items: raise Exception()
			url = items[0].get('next', '')
			if url == '': raise Exception()
			url_params = dict(parse_qsl(urlsplit(url).query))
			nextMenu = getLS(32053)
			page = '  [I](%s)[/I]' % url_params.get('page')
			nextMenu = '[COLOR skyblue]' + nextMenu + page + '[/COLOR]'
			icon = control.addonNext()
			url = '%s?action=movies_PublicLists&url=%s' % (sysaddon, quote_plus(url))
			item = control.item(label=nextMenu, offscreen=True)
			item.setArt({'icon': icon, 'thumb': icon, 'poster': icon, 'banner': icon})
			item.setProperty ('SpecialSort', 'bottom')
			control.addItem(handle=syshandle, url=url, listitem=item, isFolder=True)
		except:
			from resources.lib.modules import log_utils
			log_utils.error()

		skin = control.skin
		if skin == 'skin.arctic.horizon': pass
		elif skin in ('skin.estuary', 'skin.aeon.nox.silvo'): content = ''
		elif skin == 'skin.auramod':
			if content not in ('actors', 'genres'): content = 'addons'
			else: content = ''
		control.content(syshandle, content) # some skins use their own thumb for things like "genres" when content type is set here
		control.directory(syshandle, cacheToDisc=True)