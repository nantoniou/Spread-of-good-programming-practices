import sys
import os
sys.path.insert(0, '../oscar.py')

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
	
#	if type == 'tree':
#		return [blob.split(';') for blob in out.strip().split('\n')]
	if type == 'commit':#elif
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
	query = 'echo ' + tree_hash + ' | ~/lookup/showCnt tree | grep "' + '\|'.join(ci_files) +'"'
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
		if count % 50 == 0:
			print count, ' / ', len(commits) - 1
	
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
	We use unix commands to achieve a better performance.
	"""
	# delete contents
	open('modifications.csv', 'w').close()
	open('introductions.csv', 'w').close()

	for count, commit in enumerate(commits):
		# status update
		#if (count + 1) % 50 == 0:
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
			" grep '" + "\|".join(ci_files) +"'")
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
			


def find_links(author, end_time, method='sh'):
	"""
	Method used to find the neighbours of a given author, i.e. the authors that
	affected the given author's use of good coding practices.
	A timestamp is also given to define the time till which we find the connections.
	"""
	out = bash('echo "'+ author + '" | ~/lookup/getValues a2p')
	pr = [x for x in out.strip().split(';')[1:]]
	
	#TODO handle forks
	
	if method == 'pr_timeline':		
		p = Proj()
		for project in pr:
			rows = p.project_timeline(['time','repo', 'author'], project)
			for row in rows:
				print row

def calculate_metrics(author):
	# getting the author's commits
	out = bash('echo "'+ author + '" | ~/lookup/getValues a2c')
	commits = [x for x in out.strip().split(';')[1:]]
	
	calc_CI(commits, author)
	

# checking whether the user provided the author
if len(sys.argv) == 1:
	sys.exit('No author provided')

calculate_metrics(sys.argv[1])
#calc_CI(['bfb1c6715b5b5698b599ab5e54e5c87d46128679'], sys.argv[1])
