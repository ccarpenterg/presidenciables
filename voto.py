
from decimal import *
import csv
import os
import random
#import md5
import hashlib
import Cookie
import time
from google.appengine.ext.webapp import template
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app

class Candidato(db.Model):
    name = db.StringProperty()
    group = db.StringProperty()
    img_id = db.StringProperty()


class Round(db.Model):
    candidatos = db.StringListProperty()


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

class User(db.Model):
    id = db.StringProperty()
    datecreated = db.DateTimeProperty(auto_now_add=True)
    ip = db.StringProperty()
    unvoted = db.StringListProperty()

def increment_counter(key):
    obj = db.get(key)
    obj.scoring += 1
    obj.put()

class MainPage(webapp.RequestHandler):
    def get(self):
	path = os.path.join(os.path.dirname(__file__), 'index.html')
	self.response.out.write(template.render(path, None))

class CookieHandler(webapp.RequestHandler):
    def get(self):
	m = hashlib.md5()
	m.update(self.request.headers['User-Agent'])
	m.update(self.request.remote_addr)
	temp = ''
	for key, value in self.request.headers.items():
	    temp += key + ' - ' + value + '</br>'
	temp += 'IP: ' + self.request.remote_addr + '</br>'
	temp += m.hexdigest() + '</br>'
	#if self.request.get('set-cookie', default_value=None) == None:
	if 'pollid' not in self.request.cookies:
	    cookie = Cookie.SimpleCookie()
	    cookie['pollid'] = m.hexdigest()
	    #cookie['pollid']['expires'] = 300
	    cookie['pollid']['max-age'] = 300
	    self.response.headers.add_header('Set-Cookie', cookie['pollid'].OutputString()) 
	temp += self.request.cookies['pollid']
	self.response.out.write(temp)

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
	if 'pollid' not in self.request.cookies:
            cookie = Cookie.SimpleCookie()
            cookie['pollid'] = id
            cookie['pollid']['max-age'] = 30000
            self.response.headers.add_header('Set-Cookie', cookie['pollid'].OutputString())
	    user = User()
	    user.id = m.hexdigest()
	    user.ip = self.request.remote_addr

	    query = db.Query(Rounds)
	    num = query.count()
	    rounds = query.fetch(num)
	    unvoted = []
	    for round in rounds:
		unvoted.append(round.key().__str__())

	    user.unvoted = unvoted
	    user.put()
	#################################
	# identify user and query polls #
	#################################
	if 'pollid' in self.request.cookies: id = self.request.cookies['pollid']
	query = User.all()
	query.filter("id =", id)
	user = query.get()
	unvoted = user.unvoted
	if len(unvoted) == 0: self.redirect('/results')
	round = random.sample(unvoted, 1)[0]
	unvoted.remove(round)
	round = db.get(round)
	user.unvoted = unvoted
	user.put()


	template_values = {
	    'id_a' : round.candidato_a.key(),
	    'id_b' : round.candidato_b.key(),
	    'img_a': 'img/' + round.candidato_a.img_id + '.jpg',
	    'img_b': 'img/' + round.candidato_b.img_id + '.jpg',
	    'name_a': round.candidato_a.name,
	    'name_b': round.candidato_b.name,
	    'results': "35%".encode('utf-8'),
	    'round': round.key()
	    }
	path = os.path.join(os.path.dirname(__file__), 'templatev1.html')
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
	'''
	query = Poll.all()
        query.filter("usr_id =", usr_id)
        num = query.count()
        rounds_voted = set()
        voted = query.fetch(num)
        for round in voted:
            rounds_voted.add(round.round.key())
        query = db.Query(Rounds)
        num = query.count()
        rounds = query.fetch(num)
        all_rounds = set()
        for round in rounds:
            all_rounds.add(round.key())
        not_voted = all_rounds - rounds_voted
        not_voted = list(not_voted)
        num = len(not_voted)
        x = random.randint(0, num - 1)
        key = not_voted[x]
        round = db.get(key)
	'''
	
	query = User.all()
        query.filter("id =", usr_id)
        user = query.get()
        unvoted = user.unvoted
        if not unvoted: self.redirect('/results')
        round = random.sample(unvoted, 1)[0]
        unvoted.remove(round)
        round = db.get(round)
        user.unvoted = unvoted
        user.put()


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
	score_a = (Decimal(score_a.scoring) / Decimal(score_total)) * 100
	score_b = (Decimal(score_b.scoring) / Decimal(score_total)) * 100

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
	    'result_a': score_a.__str__() + '%',
	    'result_b': score_b.__str__() + '%',
	    'tag_a': tag_left,
	    'tag_b': tag_right,
	    'round': round.key()
            }
        path = os.path.join(os.path.dirname(__file__), 'ajax.html')
        self.response.out.write(template.render(path, template_values))


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
	    

class DeleteHandler(webapp.RequestHandler):
    def get(self):
	candidatos = db.GqlQuery("SELECT * FROM Candidato")
	for candidato in candidatos:
	    candidato.delete()
	self.response.out.write('OK')

class ShowData(webapp.RequestHandler):
    def get(self):
	query = db.Query(Poll)
	num = query.count()
	query.order('usr_id')
	temp = ''
	for poll in query.fetch(num):
	    temp += poll.vote.name + ' ' + str(poll.round.key())  + '</br>'
	self.response.out.write(temp)

application = webapp.WSGIApplication(
				     [('/', MainPage),
				      ('/load', LoadHandler),
				      ('/show', ShowHandler),
				      ('/delete', DeleteHandler),
				      ('/round', RoundHandler),
				      ('/ajax', AjaxHandler),
				      ('/cookie', CookieHandler),
				      ('/showdata', ShowData),
				      ('/init', InitCounters)],
				     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
