import argparse
import json
import math
import urllib
import urllib2
import random
import re
import subprocess
import sys
import time
from StringIO import StringIO
from gensim.models import KeyedVectors

parser = argparse.ArgumentParser()
parser.add_argument('--mp3_player', dest='mp3_player', type=str, default='', help='a command that will silently play an mp3 file on your system; this enables speech mode')
parser.add_argument('--pre_words', dest='pre_words', type=str, default='', help='25 words to pre-load the board with, if desired')
parser.add_argument('--seed', dest='seed', type=str, default='', help='a seed for the board randomizer')

args = parser.parse_args(sys.argv[1:])
seed = args.seed
SAY_CMD = args.mp3_player
pre_words = args.pre_words.strip().split()

if len(pre_words) > 0 and len(pre_words) != 25:
	print "please enter exactly 25 words for pre_words"
	quit()


stop_words = set(['a', 'an', 'the', '', 'of', 'on', 'or', 'for', 'is', 'no', 'and'])
assoc_cache = dict()
eng = set()

if seed != '':
	random.seed(seed)

# say says stuff
def say(s):
	subprocess.call("curl -s 'https://translate.google.com/translate_tts?ie=UTF-8&q=%s&tl=en&client=tw-ob' -H 'Referer: http://translate.google.com/' -H 'User-Agent: stagefright/1.2 (Linux;Android 5.0)' > google_tts.mp3 && %s google_tts.mp3" % (urllib.quote(s), SAY_CMD), shell = True)

# assoc fetches a bunch of associated words from ConceptNet
def assoc(the_word):
	if the_word in assoc_cache:
		return assoc_cache[the_word]

	response = urllib2.urlopen('http://api.conceptnet.io/c/en/%s?offset=0&limit=10000' % the_word)
	resp = response.read()


	exp = re.findall('(?:\[\[([^\]]*)\]\])', resp)

	assoc = set()

	for e in exp:
		for word in re.sub(r'[^a-zA-Z ]', '', e).split(" "):
			if word.lower() not in stop_words and word in eng and word in model.wv.vocab:
				assoc.add(word.lower())

	assoc_cache[the_word] = assoc
	return assoc


# print_board's functionality is undefined.
def print_board(words):
	col_width = [0]*5
	for col in range(5):
		max_length = 0
		for row in range(5):
			w = words[row*5+col]
			if len(w) > max_length:
				max_length = len(w)
		col_width[col] = max_length

	for row in range(5):
		for col in range(5):
			w = words[row*5+col]
			print w + (' ' * (col_width[col]-len(w)+1)),
		print ""
	print ""



print "loading english dictionary..."
with open('eng-words.txt', 'r') as f:
	for line in f.readlines():
		eng.add(line.strip().lower())
print "done"




print "loading semantic vector space..."
model = KeyedVectors.load_word2vec_format('GoogleNews-vectors-negative300.bin', binary=True)
print "done"



print "loading codenames words..."
gwords = set()
with open('game-words.txt', 'r') as f:
	for l in f.readlines():
		gwords.add(l.strip().lower())
words = random.sample(gwords, 25)
print "done"

if seed == 'original':
	words = 'trip vet robin wake space bug thief hospital stock shakespeare card gas fly bow bill mouse cloak figure soldier bar model snowman jam ham green'.split()

if len(pre_words) == 25:
	words = pre_words


print "priming association cache..."
for w in words:
	assoc(w)
print "done"
print ""


print_board(words)

while True:
	try:
		inp = raw_input('> ')
		if inp == "":
			continue

		splinp = inp.strip().split()
		if splinp[0] == "RESET":
			if len(splinp) == 1:
				print "please enter a seed to reset to"
				print ""
				continue
			random.seed(splinp[1])
			print "resetting with seed %s..." % splinp[1]
			print ""
			words = random.sample(gwords, 25)
			print_board(words)
			print ""
			print ""
			continue

		if inp == "BOARD":
			print ""
			print_board(words)
			print ""
			print ""
			continue

		linp = inp.strip().split()
		if len(linp) != 2:
			print "please enter a word and a number"
			continue

		word = linp[0]
		num = -1

		try:
			num = int(linp[1])
		except ValueError:
			print "please enter a word and a number"
			continue

		if num < 1 or num > 25:
			print "please enter a number between 1 and 25 (inclusive)"


		t1 = time.time()


		# SCORE COMPONENT #1: word association
		# loop over all pairs of associated words and accumulate semantic distances
		# x4 weight to compensate for observed empirical maxima
		word_assoc = assoc(word)
		ranked = []
		ranked_dict = dict()
		for candidate in words:
			cand_assoc = assoc(candidate)
			score = 0
			count = 0
			for w1 in word_assoc:
				for w2 in cand_assoc:
					score += model.wv.similarity(w1, w2)**2
					count += 1
			score = math.sqrt(score*1.0/count)
			score = 4 * score
			ranked.append((candidate, score))
			ranked_dict[candidate] = score


		# SCORE COMPONENT #2: word distance
		# just compare the semantic distances of candidate words to the input word
		simple_ranked = []
		simple_ranked_dict = dict()
		if word not in model.wv.vocab:
			for cand in words:
				simple_ranked.append((cand, 0))
				simple_ranked_dict[cand] = 0
		else:
			for candidate in words:
				score = model.wv.similarity(candidate, word)
				simple_ranked.append((candidate, score))
				simple_ranked_dict[candidate] = score


		# square and combine the scores for our final ranking
		comb_rank = []
		for cand in words:
			comb_score = ranked_dict[cand]**2 + simple_ranked_dict[cand]**2
			comb_rank.append((cand, comb_score))


		if SAY_CMD != "":
			print '(guess took %.2f seconds)' % (time.time()-t1)
			print ""
			guesses = sorted(comb_rank, key = lambda x: x[1], reverse = True)[:num]
			for i in range(len(guesses)):
				guess = guesses[i]
				print guess[0]
				say(guess[0])
				if i < len(guesses)-1:
					inp = raw_input()
					if inp.lower() == "stop":
						break
		else:
			print ', '.join([x[0] for x in sorted(comb_rank, key = lambda x: x[1], reverse = True)][:num])
			print '(guess took %.2f seconds)' % (time.time()-t1)
			print ""

	except KeyboardInterrupt:
		quit()
	except:
		print "something's wrong:"
		print sys.exc_info()[0]
		continue
