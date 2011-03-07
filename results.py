from decimal import *

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app

class Candidato(db.Model):
    name = db.StringProperty()
    group = db.StringProperty()
    img_id = db.StringProperty()

class Rounds(db.Model):
    candidato_a = db.ReferenceProperty(Candidato,
        collection_name="rounds_reference_one_set")
    candidato_b = db.ReferenceProperty(Candidato,
        collection_name="rounds_reference_two_set")

class PollOption(db.Model):
    round = db.ReferenceProperty(Rounds)
    candidate = db.ReferenceProperty(Candidato)

class Poll(db.Model):
    round  = db.ReferenceProperty(Rounds)
    vote   = db.ReferenceProperty(Candidato)
    usr_id = db.StringProperty()
    timestamp = db.DateTimeProperty(auto_now_add=True)

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

class ResultHandler(webapp.RequestHandler):
    def get(self):
	rounds = db.Query(Rounds)
	for round in rounds:
	    taskqueue.add(url='/worker/result', params={'round': round.key().__str__()}, queue_name='results')

class ResultWorker(webapp.RequestHandler):
    def post(self):
	round = self.request.get('round')
	round = db.get(round)
        query = db.Query(PollScoring)
        query.filter("round =", round.key())
        query.filter("candidato =", round.candidato_a.key())
        score_a = query.get()
        query = db.Query(PollScoring)
        query.filter("round =", round.key())
        query.filter("candidato =", round.candidato_b.key())
        score_b = query.get()
        score_total = score_a.scoring + score_b.scoring
        getcontext().prec = 4
        score_a_ratio = (Decimal(score_a.scoring) / Decimal(score_total)) * 100
        score_b_ratio = (Decimal(score_b.scoring) / Decimal(score_total)) * 100
        template_values = {
                'name_a': round.candidato_a.name,
                'name_b': round.candidato_b.name,
                'img_res_a': '/img/' + round.candidato_a.img_id + '.jpg',
                'img_res_b': '/img/' + round.candidato_b.img_id + '.jpg',
                'result_a': score_a_ratio.__str__() + '%',
                'result_b': score_b_ratio.__str__() + '%',
                #'tag_a': tag_left,
                #'tag_b': tag_right,
                'votes_a': score_a.scoring,
                'votes_b': score_b.scoring,
                'round': round.key()
                }
	memcache.set(round.key().__str__(), template_values)

application = webapp.WSGIApplication(
					[('/worker/result', ResultWorker),
					 ('/results', ResultHandler)],
					debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()




