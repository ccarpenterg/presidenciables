from datetime import datetime, timedelta
from decimal import *
from copy import deepcopy
import csv
import os
import random
import hashlib
import Cookie
import time
from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app

from google.appengine.api import memcache

class Candidato(db.Model):
    name = db.StringProperty()
    group = db.StringProperty()
    img_id = db.StringProperty()


class Rounds(db.Model):
    candidato_a = db.ReferenceProperty(Candidato,
	collection_name="rounds_reference_one_set")
    candidato_b = db.ReferenceProperty(Candidato,
	collection_name="rounds_reference_two_set")

class Poll(db.Model):
    round  = db.ReferenceProperty(Rounds)
    vote   = db.ReferenceProperty(Candidato)
    usr_id = db.StringProperty()

class PollScoring(db.Model):
    candidato = db.ReferenceProperty(Candidato)
    round     = db.ReferenceProperty(Rounds)
    scoring   = db.IntegerProperty()

class Voter(db.Model):
    id = db.StringProperty()
    datecreated = db.DateTimeProperty(auto_now_add=True)
    ip = db.StringProperty()
    actived = db.BooleanProperty()
    voted = db.ListProperty(long)

def increment_counter(key):
    obj = db.get(key)
    obj.scoring += 1
    obj.put()

def get_rounds():
    data = memcache.get('rounds')
    if data is not None:
	return data
    else:
	data = []
	query = db.Query(Rounds)
	num = query.count()
	rounds = query.fetch(num)
	for round in rounds:
	    data.append(round.key().id())
	memcache.add('rounds', data)
	return data

class MainPage(webapp.RequestHandler):
    def get(self):
	path = os.path.join(os.path.dirname(__file__), 'index.html')
	self.response.out.write(template.render(path, None))


class RoundHandler(webapp.RequestHandler):
    def get(self):
	##############################
	# create user and set cookie #
	##############################
	m = hashlib.md5()
        m.update(self.request.headers['User-Agent'])
        m.update(self.request.remote_addr)
	m.update(str(int(time.time()*10000000)))
	id = m.hexdigest()
	#if 'pollid' not in self.request.cookies.keys():
	if self.request.cookies.get('pollid', None) == None:
            cookie = Cookie.SimpleCookie()
            cookie['pollid'] = id
            #cookie['pollid']['max-age'] = 30000
	    expires = datetime.now() + timedelta(days=4)
	    cookie['pollid']['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S')
	    cookie['pollid']['path'] = '/'
            self.response.headers.add_header('Set-Cookie', cookie['pollid'].OutputString())
	    #self.response.headers.add_header('Set-Cookie', 'pollid=%s; Max-Age=30000' % id)
	    newvoter = Voter()
	    newvoter.id = id
	    newvoter.ip = self.request.remote_addr
	    newvoter.actived = False
	    newvoter.voted = []
	    newvoter.put()
	    unvoted = get_rounds()
	else:
	    id = self.request.cookies.get('pollid')
	    query = Voter.all()
	    query.filter("id =", id)
	    voter = query.get()
	    voted = voter.voted
	    all_rounds = get_rounds()
	    unvoted = set(all_rounds) - set(voted)

	#################################
	# identify user and query polls #
	#################################
	round = random.sample(list(unvoted), 1)[0]
	round = Rounds.get_by_id(round)

	query = Voter.all()
	query.filter("actived =", True)
	num_users_actived = query.count()

	template_values = {
	    'id_a' : round.candidato_a.key(),
	    'id_b' : round.candidato_b.key(),
	    'img_a': 'img/' + round.candidato_a.img_id + '.jpg',
	    'img_b': 'img/' + round.candidato_b.img_id + '.jpg',
	    'name_a': round.candidato_a.name,
	    'name_b': round.candidato_b.name,
	    'users': num_users_actived.__str__(),
	    'round': round.key()
	    }
	path = os.path.join(os.path.dirname(__file__), 'template.html')
        self.response.out.write(template.render(path, template_values))

class AjaxHandler(webapp.RequestHandler):
    def post(self):
	#####################################
	# get candidato.key() and save poll #
	#####################################
	usr_id = self.request.cookies['pollid']
	id = self.request.get("id")
	lastround = self.request.get("round")
	result = db.get(id)
	lastround = db.get(lastround)
	poll = Poll()
	poll.round = lastround.key()
	poll.vote = result.key()
	poll.usr_id = usr_id
	poll.put()

	################################
	# run trx to increment scoring #
	################################
	query = db.Query(PollScoring)
	query.filter("round =", lastround.key())
	query.filter("candidato =", result.key())
	score = query.get()
	increment_counter(score.key())

	####################
	# query left polls #
	####################
	query = Voter.all()
        query.filter("id =", usr_id)
        user = query.get()
	all_rounds = set(get_rounds())
	voted = deepcopy(user.voted)
	voted.append(lastround.key().id())
	unvoted = all_rounds - set(voted)
        if lastround.key().id() not in user.voted:
	    if not user.actived: user.actived = True
	    user.voted = voted
	    user.put()
	query = Voter.all()
	query.filter("id =", usr_id)
	voter = query.get()
	if len(all_rounds) == len(voter.voted): 
	    self.response.set_status(303)
	else:
            round = random.sample(list(unvoted), 1)[0]
            round = Rounds.get_by_id(round)


	#################################
	# score_a, score_b, score_total #
	#################################
	    query = db.Query(PollScoring)
	    query.filter("round =", lastround.key())
	    query.filter("candidato =", lastround.candidato_a.key())
	    score_a = query.get()
	    query = db.Query(PollScoring)
	    query.filter("round =", lastround.key())
	    query.filter("candidato =", lastround.candidato_b.key())
	    score_b = query.get()
	    score_total = score_a.scoring + score_b.scoring
	    getcontext().prec = 4
	    score_a_ratio = (Decimal(score_a.scoring) / Decimal(score_total)) * 100
	    score_b_ratio = (Decimal(score_b.scoring) / Decimal(score_total)) * 100

	    tag_right = 'yes'
	    tag_left  = 'no'
	    if lastround.candidato_a.key() == result.key():
	        tag_right = 'no'
	        tag_left  = 'yes'
            template_values = {
                'id_a' : round.candidato_a.key(),
                'id_b' : round.candidato_b.key(),
                'img_a': 'img/' + round.candidato_a.img_id + '.jpg',
                'img_b': 'img/' + round.candidato_b.img_id + '.jpg',
	        'name_a': round.candidato_a.name,
                'name_b': round.candidato_b.name,
	        'img_res_a': 'img/' + lastround.candidato_a.img_id + '.jpg',
	        'img_res_b': 'img/' + lastround.candidato_b.img_id + '.jpg',
	        'result_a': score_a_ratio.__str__() + '%',
	        'result_b': score_b_ratio.__str__() + '%',
	        'tag_a': tag_left,
	        'tag_b': tag_right,
		'votes_a': score_a.scoring,
		'votes_b': score_b.scoring,
	        'round': round.key()
                }
            path = os.path.join(os.path.dirname(__file__), 'ajax.html')
            self.response.out.write(template.render(path, template_values))

class ResultsHandler(webapp.RequestHandler):
    def get(self):
	tmp = ''
	results = []
	query = Rounds.all()
	num = query.count()
	rounds = query.fetch(num)
	for round in rounds:
	    query = db.Query(PollScoring)
	    query.filter('round =', round.key())
	    for poll in query.fetch(2):
		tmp += poll.candidato.name + poll.round.key().__str__() + poll.scoring.__str__() + '</br>'
	self.response.out.write(tmp)

class LoadHandler(webapp.RequestHandler):
    def get(self):
	reader = csv.reader(open('data.csv', 'r'), delimiter=',')
	for row in reader:
	    c = Candidato()
	    c.name = row[0].decode('utf-8')
	    c.group = row[1].decode('utf-8')
	    c.img_id = row[3]
	    c.put()
	self.response.out.write('OK')

class ShowHandler(webapp.RequestHandler):
    def get(self):
	temp = ''
	left = db.GqlQuery("SELECT * FROM Candidato WHERE group = :group", group="Concertacion")
	right = db.GqlQuery("SELECT * FROM Candidato WHERE group = :group", group="Alianza")
	pro  = db.GqlQuery("SELECT * FROM Candidato WHERE group = :group", group="Pro")
	for c1 in right:
	    for c2 in left:
		#temp += c1.name + ' vs ' + c2.name + '</br>'
		r = Rounds()
		#r.candidatos = [c1.name, c2.name]
		r.candidato_a = c1.key()
		r.candidato_b = c2.key()
		r.put()
	for c1 in pro:
	    for c2 in left:
                #temp += c1.name + ' vs ' + c2.name + '</br>'
		r = Rounds()
                #r.candidatos = [c1.name, c2.name]
		r.candidato_a = c1.key()
                r.candidato_b = c2.key()
                r.put()
	    for c2 in right:
                #temp += c1.name + ' vs ' + c2.name + '</br>'
		r = Rounds()
                #r.candidatos = [c1.name, c2.name]
		r.candidato_a = c1.key()
                r.candidato_b = c2.key()
                r.put()
	#vs1 = db.GqlQuery("SELECT * FROM Candidato")
	#for c1 in vs1:
	#    vs2 = db.GqlQuery("SELECT * FROM Candidato WHERE group != :group", group=c1.group)
	#    for c2 in vs2:
	#	temp += c1.name + ' vs ' + c2.name + '</br>'
	#temp = ''
	#for candidato in candidatos:
	#    temp += candidato.name + ' ' + candidato.key().__str__()  + '</br>'
	rounds = db.GqlQuery("SELECT * FROM Rounds")
	for round in rounds:
	    #temp += round.candidatos[0] + ' vs ' + round.candidatos[1] + '</br>'
	    temp += round.candidato_a.name + ' vs ' + round.candidato_b.name + '</br>'
	self.response.out.write(temp)

class InitCounters(webapp.RequestHandler):
    def get(self):
	
	query = db.Query(Rounds)
	num = query.count()
	rounds = query.fetch(num)
	for round in rounds:
	    score = PollScoring()
	    score.candidato = round.candidato_a.key()
	    score.round = round.key()
	    score.scoring = 0
	    score.put()
	    score = PollScoring()
	    score.candidato = round.candidato_b.key()
	    score.round = round.key()
	    score.scoring = 0
	    score.put()
	
	query = db.Query(PollScoring)
	num = query.count()
	scores = query.fetch(num)
	temp = ''
	for score in scores:
	    temp += score.candidato.name + ' -> ' + score.scoring.__str__() + '</br>'
	'''
	scores = db.GqlQuery("SELECT * FROM PollScoring")
	for score in scores:
	    score.delete()
	temp = 'OK'
	'''
	self.response.out.write(temp)
	    

class FlushHandler(webapp.RequestHandler):
    def get(self):
	memcache.flush_all()
	self.response.out.write('OK')

application = webapp.WSGIApplication(
				     [('/', MainPage),
				      ('/load', LoadHandler),
				      ('/show', ShowHandler),
				      ('/vote', RoundHandler),
				      ('/ajax', AjaxHandler),
				      ('/init', InitCounters),
				      ('/resultados', ResultsHandler),
				      ('/flush', FlushHandler)],
				     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
