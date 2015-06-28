### IMPORTS ###
import OAuth2Util
import praw
import re
import sys
import threading
import time
import traceback
from wordnik import *
from datetime import datetime

### CLASS ###
class Define_It:
	def __init__(self, reddit, footer='', sidebar='', username='', subreddit=''):
		self._r = reddit
		self._o = OAuth2Util.OAuth2Util(self._r)
		
		self._done = DoneList()
		self._avoid = AvoidList()
		
		self.message_footer = footer
		self.sidebar = sidebar
		self.match_pattern = re.compile(r'(?:\n|^)define(?:: ?| )(-ignore|(?:["*\']+)?([^\n,.!?#&_:;"*\\(){}<>[\]]+))(, ?((pro)?noun|(ad)?verb(-(in)?transitive)?|adjective|abbreviation|(preposi|conjunc|interjec)tion))?')
		
		self._load_dictionary()
		self._create_api()
		
		self.username = username
		self.subreddit = subreddit
	
	# ### WORDNIK ### #
	def _load_dictionary(self):
		try:
			with open('define_it.conf','r') as f:
				lines = [x.strip() for x in f.readlines()]
			self._api_url,self._api_key = lines
		except OSError:
			print('Could not find config file.')
	
	def _create_api(self):
		self._client = swagger.ApiClient(self._api_key,self._api_url)
		self._wordApi = WordApi.WordApi(self._client)
	
	# ### REDDIT ### #
	def search(self, body):
		found = self.match_pattern.search(body)
		return found is not None
	
	def _strip_unwanted(self, word):
		if isinstance(word, str):
			try:
				if (word[0] == word[-1] and
					word[0] in '"*\''):
					word = word[1:-1]
				if ' - ' in word:
					word = word.split('-')[0].strip()
				return word
			except IndexError as e:
				Error(e, tb=traceback)
	
	def _make(self, body):
		pat = re.compile(r' ?(because|but|please).*',re.IGNORECASE)
		found = self.match_pattern.search(body)
		if found is None:
			return
		if found.group(3) != None:
			return re.sub('["*]+','',body[found.start():found.end()].lstrip()[7:].strip()).split(',')
		body = re.sub('["*]+','',body[found.start():found.end()].lstrip()[7:].strip())
		if len(body.split(' ')) > 1:
			return pat.sub('', self._strip_unwanted(body))
		return self._strip_unwanted(body)
	
	def ignore(self, comment):
		self._avoid.add(comment.author.name)
		comment.reply('This message confirms that you have been added to the ignore list.' + self.message_footer)
	
	def delete(self, comment):
		if comment.is_root:
			return
		parent_id = comment.parent_id
		parent = self._r.get_info(thing_id=parent_id)
		if parent.author.name != self.username:
			return
		request_id = parent.parent_id
		request = self._r.get_info(thing_id=request_id)
		if comment.author.name != request.author.name:
			return
		parent.delete()
		print('%s requested comment get deleted'%comment.author.name)
	
	def _begin(self, comment):
		id = comment.id
		already_done = self._done.get()
		avoid = self._avoid.get()
		if id not in already_done:
			self._done.add('%s\n'%id)
			author = comment.author.name
			body = re.sub(r'/u/%s'self.username,'define',comment.body,flags=re.IGNORECASE)
			formatted = self._make(body)
			if formatted != None and author not in avoid:
				if isinstance(formatted, list):
					word = formatted[0]
					if word == '-ignore':
						self.ignore(comment)
						return
					elif word == '-delete':
						self.delete(comment)
						return
					part = formatted[1]
				else:
					if formatted == '-ignore' and author not in avoid:
						self.ignore(comment)
						return
					elif formatted == '-delete':
						self.delete(comment)
						return
					word = formatted
					part = ''
				self._create_api()
				partText = part if part == '' else (' as a ' + part)
				definitions = Definition(self._wordApi, word=word, part=part)
				formatted = definitions.format()
				if len(definitions.definitions) > 0:
					print('%s requested "%s"%s'%(author,word,partText))
					comment.reply(formatted + self.message_footer)
					try:
						self._r.get_subreddit(self.subreddit).update_settings(description=self.sidebar.format(requester=author,definitions=formatted))
					except Exception as e:
						Error(e, tb=traceback)
	
	def run(self):
		self._o.refresh()
		while True:
			try:
				for x in praw.helpers.comment_stream(self._r, 'all'):
					self._o.refresh()
					if not self.search(x.body): continue
					t2 = threading.Thread(target=self._begin(x))
					t2.start()
					time.sleep(5)
					try:
						zzz = next(self._r.get_unread())
						messages = True
					except StopIteration:
						messages = False
					if messages:
						for y in self._r.get_unread():
							try:
								y.mark_as_read()
								if y.subject == 'comment reply' or (y.subject == 'username mention' and y.was_comment):
									t3 = threading.Thread(target=self._begin(y))
									t3.start()
							except AttributeError:
								pass
			except praw.errors.Forbidden:
				pass
			except KeyboardInterrupt:
				print('Exiting...')
				sys.exit(-1)

class Definition:
	def __init__(self, api, **kwargs):
		self._api = api
		if 'word' in kwargs and 'part' in kwargs:
			self.word = kwargs['word']
			self.definitions = self.define(kwargs['word'],kwargs['part'])
	
	def define(self, word, part):
		f = self._api.getDefinitions
		definitions = []
		for i in range(3):
			try:
				d = f(word, partOfSpeech=part, sourceDictionaries='all')
				if d is None:
					d = f(word.lower(), partOfSpeech=part, sourceDictionaries='all')
					if d is not None:
						definitions.append((d[i].word,d[i].partOfSpeech,d[i].text))
						continue
					d = f(word.upper(), partOfSpeech=part, sourceDictionaries='all')
					if d is not None:
						definitions.append((d[i].word,d[i].partOfSpeech,d[i].text))
						continue
					d = f(word.capitalize(), partOfSpeech=part, sourceDictionaries='all')
					if d is not None:
						definitions.append((d[i].word,d[i].partOfSpeech,d[i].text))
						continue
					break
				definitions.append((d[i].word,d[i].partOfSpeech,d[i].text))
			except IndexError as e:
				Error(e,tb=traceback)
				break
			except Exception:
				break
		return definitions
	
	def format(self):
		s = ''
		if len(self.definitions) >= 1:
			for definition in self.definitions:
				word = definition[0]
				if definition[1] != 'abbreviation':
					word = ' '.join([x.capitalize() for x in word.split(' ')])
				s += '%s (%s): %s\n\n' % (word, definition[1], definition[2])
		return s

class DoneList:
	def __init__(self):
		self.list = self.get()
	
	def add(self,content,a=True):
		if a:
			self.read()
		with open('done.txt', 'a') as f:
			f.write(content)
	
	def read(self):
		with open('done.txt') as f:
			for i,l in enumerate(f):
				pass
		if (i+1) >= 200000:
			t = self._tail(open('done.txt'), 50000)
			open('done.txt', 'w').close()
			for x in t[0]:
				self.add('%s\n'%x,False)
	
	def _tail(self, f, n, offset=None):
		avg_line_length = 7
		to_read = n + (offset or 0)
		while 1:
			try:
				f.seek(-(avg_line_length * to_read), 2)
			except IOError:
				f.seek(0)
			pos = f.tell()
			lines = f.read().splitlines()
			if len(lines) >= to_read or pos == 0:
				f.close()
				return lines[-to_read:offset and -offset or None], \
						len(lines) > to_read or pos > 0
			avg_line_length *= 1.3
	
	def get(self):
		with open('done.txt') as f:
			return [x.strip() for x in f.readlines()]

class AvoidList:
	def __init__(self):
		self.list = self.get()
	
	def add(self, name):
		with open('avoid.txt', 'a') as f:
			f.write('%s\n'%name)
	
	def get(self):
		with open('avoid.txt') as f:
			return [x.strip() for x in f.readlines()]

class Error:
	def __init__(self, error, message=None, tb=None):
		if message is not None:
			print(str(type(error)) + ' ' + message)
		else:
			print(str(type(error)))
		if tb is not None:
			d = datetime.now()
			name = 'errors\\error{0}.txt'.format(d.strftime('%Y%m%d%H%M%S'))
			f = open(name, 'w')
			tb.print_exc(file=f)
			f.close()