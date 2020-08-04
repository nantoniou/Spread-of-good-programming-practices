import sys
import os
sys.path.insert(0, '../oscar.py')

import re
from oscar import Project
from oscar import Time_project_info as Proj
import subprocess

from time import time as current_time
start_time = current_time()

def bash(command):
	proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
	(out, err) = proc.communicate()
	return out

def search(hash, type):
	"""
	Method used to search for a specific blob, commit or tree.
	
	If a tree is searched for, the result is splitted into its components (blobs and directories),
	which are again splitted into their mode, hash and name.
	
	In the case of a commit, we split the information string and the tree hash and
	parent's commit hash are returned
	"""
	out = bash('echo ' + hash + ' | ~/lookup/showCnt ' + type)
	
	if type == 'tree':
		return [blob.split(';') for blob in out.strip().split('\n')]
	if type == 'commit':
		splitted = out.split(';')
		# the tree and parent commit hashes are the second and third word, respectively
		# the commit time is the last word, from which we discard the timezone and cast it to int
		return splitted[1], splitted[2], int(splitted[-1].split()[0])
	return out

# files used in continuous integration
ci_files = [
	'\.gitlab\-ci\.yml', '\.travis\.yml', 'Jenkinsfile', 'buddy\.yml', '\.drone\.yml',
	'circle\.yml', '\.circleci', 'bamboo\.yaml', 'codeship\-steps\.yml', '\.teamcity',
	'wercker\.yml', 'appveyor\.yml', 'bitrise\.yml', 'codefresh\.yml', 'solano\.yml',
	'shippable\.yml', 'phpci\.yml', 'cloudbuild\.yaml'
]

def ci_lookup(tree_hash):
	"""
	Method used to check the usage of Continuous Integration in a tree, given its hash.
	"""	
	query = 'echo ' + tree_hash + ' | ~/lookup/showCnt tree | egrep "' + '|'.join(ci_files) +'"'
	out = bash(query)
	
	"""
	# alternate method
	blobs = search(tree_hash, 'tree')
	index = {'mode':1, 'hash':1, 'name':2}
	ci = False
	for blob in blobs:
		name = blob[index['name']]
		hash = blob[index['hash']]
		if ((name in ci_files) or
		    (name in ci_config_dir and ';'+ci_config_dir[name] in search(hash, 'tree'))):
			ci = True
			break
	"""
	return bool(out)

def calc_CI_introductions(commits, author):
	"""
	Alternative way to check_if_introduction, to compare performance.
	"""

	# using a dictionary that has the commits' hashes as keys,
	# so as to not search multiple times for the same commit
	CI_checked = {}

	# delete contents
	open('introductions.csv', 'w').close()
	
	# for every commit, we look up whether the author included a CI file,
	# that did not exist in the parent commit
	for count, commit in enumerate(commits):
		# status update
		if (count + 1) % 50 == 0:
			print count + 1, ' / ', len(commits)
	
		tree_hash, parent_commit_hash, time = search(commit, 'commit')
		if tree_hash not in CI_checked:
			CI_checked[tree_hash] = ci_lookup(tree_hash)
		
		# controlling for the case of multiple parent commits
		all_parent_CI = False
		for parent in parent_commit_hash.split(':'):
			# controlling for the case of no parent commits
			if parent == '':
				break
		
			parent_tree_hash = search(parent, 'commit')[0]
		
			if parent_tree_hash not in CI_checked:
				parent_CI = ci_lookup(parent_tree_hash)
				CI_checked[parent_tree_hash] = parent_CI
			else:
				parent_CI = CI_checked[parent_tree_hash]
			
			# checking all the parent commits for the usage of CI
			all_parent_CI = all_parent_CI or parent_CI
		
		# if the tree has a CI file, while the parent tree does not, increase the CI score
		if CI_checked[tree_hash] and not all_parent_CI:
			
			out = bash('echo ' + commit + ' | ~/lookup/getValues c2P')
			main_proj = out.strip().split(';')[1]
			f = open("introductions.csv", "a")
			f.write(author + ', ' + 'CI' + ', ' + str(time) + ', ' + main_proj + '\n')
			f.close()
			print 'wrote'
	print (current_time()-start_time)/len(commits), 'seconds per commit'

def check_if_introduction(commit, result):
	"""
	We check the parent commit to see if its child commit introduced or modified a CI config file.
	"""
	tree_hash, parent_commit_hash, time = search(commit, 'commit')
	
	# controlling for the case of no parent commits
	if parent_commit_hash == '':
		return True

	# controlling for the case of multiple parent commits
	all_parent_CI = False
	for parent in parent_commit_hash.split(':'):

		parent_tree_hash = search(parent, 'commit')[0]
		parent_CI = ci_lookup(parent_tree_hash)
			
		# checking all the parent commits for the usage of CI
		all_parent_CI = all_parent_CI or parent_CI
		
	# if the tree has a CI file, while the parent tree does not, it is an introduction
	return not all_parent_CI

	
def calc_CI(commits, author):
	"""
	Used to investigate how many commits, from a user, modified a CI configuration file.
	Unix commands are used for a better performance.
	"""
	# delete contents
	open('modifications.csv', 'w').close()
	open('introductions.csv', 'w').close()

	for count, commit in enumerate(commits):
		# status update
		if (count + 1) % 50 == 0:
			print commit, '..   ..', count + 1, ' / ', len(commits)

		# c2f does seems to result in a tie error, so c2b and b2f is used instead		
		#getting the blobs
		query = ("for x in $(echo " + commit + " | ~/lookup/getValues c2b |" +
			# splitting on the semicolon and discarding the newlines
			" awk -v RS='[;\\n]' 1 |" +
			# discarding the commit's hash (it appears before the blobs' hashes)
			" tail -n+2); do" +
				# for each blob, we look up it's filename
				" echo $x | ~/lookup/getValues b2f;" + 
			" done |" +
			# we discard the first field of the results (blobs' hash)
			" cut -d ';' -f2 |" +
			# we check whether one of the modified files is a CI configuration file
			" egrep '" + "|".join(ci_files) + "'")
		result = bash(query)
		if result:
			out = bash('echo ' + commit + ' | ~/lookup/getValues c2P')
			main_proj = out.strip().split(';')[1]
			time = search(commit, 'commit')[2]
				
			if check_if_introduction(commit, result):
				f = open("introductions.csv", "a")
				print 'introduction'
			else:
				f = open("modifications.csv", "a")
				print 'modification'
			f.write(author + ', ' + 'CI' + ', ' + str(time) + ', ' + main_proj + '\n')
			f.close()
			print 'wrote: -->', commit

def calc_CI_diff(commits, author):
	"""
	Method written as a faster alternative to calc_CI. It seems to be 30 times faster.
	"""
	# delete contents
	open('modifications.csv', 'w').close()
	open('introductions.csv', 'w').close()

	for count, commit in enumerate(commits):
		#status update
		if (count + 1) % 50 == 0:
			print commit, '..   ..', count + 1, ' / ', len(commits)

		# cmputeDiff2.perl seems to produce junk to the stdout occasionally
		diff = bash("echo " + commit + " | ssh da4 ~/lookup/cmputeDiff2.perl")

		# if a CI configuration file is in the diff
		if re.search("|".join(ci_files), diff):
			out = bash('echo ' + commit + ' | ~/lookup/getValues c2P')
			main_proj = out.strip().split(';')[1]
			time = search(commit, 'commit')[2]

			for blob in diff.split():
				# looking for the CI config blob and checking if parent blob exists
				if re.search("|".join(ci_files), blob):
					# if we have both an introduction and a modification
					# in the same commit, we count it as an introduction
					if blob.endswith(';'):
					# if we don't have the parent blob, after the last semicolon,
					# it is an introduction
						f = open("introductions.csv", "a")
						print 'introduction'
					else:
						f = open("modifications.csv", "a")
						print 'modification'
					break
			f.write(author + ', ' + 'CI' + ', ' + str(time) + ', ' + main_proj + '\n')
			f.close()
			print 'wrote: -->', commit

def find_links(author, end_time, method='sh'):
	"""
	Method used to find the neighbours of a given author, i.e. the authors that
	affected the given author's use of good coding practices.
	A timestamp is also given to define the time till which we find the connections.
	"""
	out = bash('echo "'+ author + '" | ~/lookup/getValues a2P')
	pr = [x for x in out.strip().split(';')[1:]]
	
	if method == 'pr_timeline':		
		p = Proj()
		for project in pr:
			rows = p.project_timeline(['time','repo', 'author'], project)
			for row in rows:
				print row

#### Start building the regular expression that will be used to search for unit testing libraries,
#### in the commit's blobs ####
# Java
java_lib = ['io.restassured', 'org.openqa.selenium', 'org.spockframework', 'jtest',
	'org.springframework.test', 'org.dbunit', 'org.jwalk', 'org.mockito', 'org.junit']
java_regex = (['import\s+'+s.replace('.', '\.') for s in java_lib])
java_all_reg = '|'.join(java_regex)

# Perl
perl_all_reg = 'use\s+Test::'

# Javascript
js = ['assert', 'mocha', 'jasmine', 'ava', 'jest', 'karma', 'storybook', 'tape',
	'cypress', 'puppeteer', 'chai', 'qunit', 'sinon', 'casper', 'buster']
js_regex = (["require\([\\\'\\\"]" + s + "[\\\'\\\"]\)" for s in js])
js_all_reg = '|'.join(js_regex)
# C#
c_sharp = ['NUnit', 'Microsoft\.VisualStudio\.TestTools\.UnitTesting',
		'Xunit', 'csUnit', 'MbUnit']
c_sharp_regex = (["using\s+" + s for s in c_sharp])
c_sharp_all_reg = '|'.join(c_sharp_regex)

# C and C++
c = ['cmocka', 'unity', 'CppuTest', 'embUnit', 'CUnit', 'CuTest', 'check',
	'gtest', 'uCUnit', 'munit', 'minunit', 'acutest', 'boost/test',
	'UnitTest\+\+', 'cpptest', 'cppunit', 'catch', 'bandit', 'tut']
c_regex = (['#include\s+[<\\\"]' + s + '\.h[>\\\"]'for s in c])
c_all_reg = '|'.join(c_regex)
# PHP
php = ['PHPUnit', 'Codeception', 'Behat', 'PhpSpec', 'Storyplayer', 'Peridot',
	'atoum', 'Kahlan', 'vendor/EnhanceTestFramework']
php_regex = (['(include|require|use).+' + s for s in php])
php_all_reg = '|'.join(php_regex)

# Python
python = ['pytest', 'unittest', 'doctest', 'testify', 'nose', 'hypothesis']
python_regex = (['import\s+'+lib+'|from\s+'+lib+'\s+import' for lib in python])
python_all_reg = '|'.join(python_regex)

all_reg = [java_all_reg, perl_all_reg, js_all_reg, c_sharp_all_reg, c_all_reg, php_all_reg, python_all_reg]
final_reg = '|'.join(all_reg)
#### End of regex building ####

def calc_test(commits, author):
	"""
	Used to investigate how many commits, from a user, modified a unit testing file.
	Unix commands are used to achieve a better performance.
	The blobs are parsed, looking for unit testing library imports. An alternative would
	be using the thruMaps directories or the ClickHouse API, but those options seem slower.
	"""
	open('modifications.csv', 'w').close()
	
	for count, commit in enumerate(commits):
		# status update
		if (count + 1) % 5 == 0:
			print commit, '..   ..', count + 1, ' / ', len(commits)

			# getting every blob from a given commit
		query = ('for x in $(echo ' + commit + ' | ~/lookup/getValues c2b | ' +
			# splitting it and discarding the newlines and the commit's hash
			'awk -v RS="[;\\n]" 1 | tail -n+2); do ' +
			# We look up the content's of each blob, and discard the STDERR,
			# in the case of trying to look up a blob that does not exist in the database
			'echo $x | ~/lookup/showCnt blob 2> /dev/null; done | ' +
			# We search for the use of a unit testing library, using the above regex, and
			# keeping the first result only, since that is enough to know that the commit contains
			# a unit testing file, to make the execution faster
			'egrep -m 1 "' + final_reg + '"')
		if bash(query): # if contains unit testing lib
			out = bash('echo ' + commit + ' | ~/lookup/getValues c2P')
			main_proj = out.strip().split(';')[1]
			time = search(commit, 'commit')[2]

			# at this point we could search the parent's tree for the existence of tests, but this
			# would require recursively looking at every directory and parsing every file in the tree, so, due
			# to the complexity, we skip it and consider it a modification instead of a possible introduction

			f = open("modifications.csv", "a")
			print 'modification'
			f.write(author + ', ' + 'TEST' + ', ' + str(time) + ', ' + main_proj + '\n')
			f.close()
			print 'wrote: -->', commit


def calc_lang_features(commits, author):
	"""
	Method used to count the usage of certain languages' good practices and modern approaches.
	We parse the diff of a modified file and the content of an introduced file, in order to find those
	practices, and we count the extent of the usage. Then, we write to a file, for each commit that
	included these features.
	"""
	lang_features = ['/\*\*', '\\"\\"\\"', '///', # documentation
			'^\s*@', 'def.+:.+->', 'using\s+System\.ComponentModel\.DataAnnotations', # assertion
			'assert', 'TODO', 'lambda']

	# delete contents
	open('lang_features.csv', 'w').close()
	
	for count, commit in enumerate(commits):
		# status update
		if (count + 1) % 5 == 0:
			print commit, '..   ..', count + 1, ' / ', len(commits)


			# for each blob modified
		query = ("for x in $(echo " + commit + " | ssh da4 ~/lookup/cmputeDiff2.perl); do " +
				# get the chold and parent blob
				"diff_blobs=$(echo $x | awk -v RS=';' 1 | sed -n '3,4 p');" +
				# if a parent blob does not exist, the author authored all of the content of the file
				"if [ $(echo $diff_blobs|wc -w) -eq 1 ]; then " +
					"echo $diff_blobs | ~/lookup/showCnt blob 2> /dev/null; " +
				# if a parent blob exists, find the diff, in order to search only the modified lines
				"elif [ $(echo $diff_blobs|wc -w) -eq 2 ]; then " +
					"vars=( $diff_blobs );" +
					# using bash instead of sh in order to use the process substitution,
					# to get the modified lines
					"/bin/bash -c \"diff <(echo ${vars[0]} | ~/lookup/showCnt blob)" +
								" <(echo ${vars[1]} | ~/lookup/showCnt blob)\";" +
				"fi;" +
			# grep the above practices and discard the lines that were deleted from the parent blob
			# (they start with ">" in diff)
			"done | egrep \"" + "|".join(lang_features) + "\" | grep -v '^>' | wc -l ")
		count_uses = int(bash(query).strip())
		if count_uses > 0: # good practice feature is used
			out = bash('echo ' + commit + ' | ~/lookup/getValues c2P')
			main_proj = out.strip().split(';')[1]
			time = search(commit, 'commit')[2]

			f = open("lang_features.csv", "a")
			print 'lang_f'
			f.write(author + ', ' + 'LANG_F' + ', ' + str(time) + ', ' + main_proj + ', ' + str(count_uses) + '\n')
			f.close()
			print 'wrote: -->', commit


def calculate_metrics(author):
	# getting the author's commits
	out = bash('echo "'+ author + '" | ~/lookup/getValues a2c')
	commits = [x for x in out.strip().split(';')[1:]]
	
	#time1 = current_time()
	#calc_CI(commits, author)
	#time2 = current_time()
	#print 'without diff time is ' + str(time2 - time1)
	#calc_CI_diff(commits, author)
	#print 'with is ' + str(current_time() - time2)
	#calc_test(commits, author)
	calc_lang_features(commits, author)

# checking whether the user provided the author
if len(sys.argv) == 1:
	sys.exit('No author provided')

calculate_metrics(sys.argv[1])

