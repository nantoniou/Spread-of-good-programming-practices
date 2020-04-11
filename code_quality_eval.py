import sys
import os
sys.path.insert(0, '../oscar.py')

from oscar import Project
import subprocess

import time
start_time = time.time()

def search(hash, type):
	"""
	Method used to search for a specific blob, commit or tree.
	
	If a tree is searched for, the result is splitted into its components (blobs and directories),
	which are again splitted into their mode, hash and name.
	
	In the case of a commit, we split the information string and the tree hash and
	parent's commit hash are returned
	"""
	proc = subprocess.Popen('echo ' + hash + ' | ~/lookup/showCnt ' + type, stdout=subprocess.PIPE, shell=True)
	(out, err) = proc.communicate()
	
	if type == 'tree':
		return [blob.split(';') for blob in out.strip().split('\n')]
	elif type == 'commit':
		splitted = out.split(';')
		# the tree and parent commit hashes are the second and third word, respectively
		return splitted[1], splitted[2]
	return out

def ci_lookup(tree_hash):
	"""
	Method used to check the usage of Continuous Integration in a tree, given its hash.
	"""
	blobs = search(tree_hash, 'tree')
	index = {'mode':1, 'hash':1, 'name':2}

	# files used in continuous integration
	ci_files = [
		'.gitlab-ci.yml', '.travis.yml', 'Jenkinsfile', 'buddy.yml', '.drone.yml',
		'circle.yml', 'bamboo.yaml', 'codeship-steps.yml'
	]

	# some tools use generic names for the configuration files, placing them in a distinct directory
	ci_config_dir = {'.circleci':'config.yml'}

	ci = False
	for blob in blobs:
		name = blob[index['name']]
		hash = blob[index['hash']]
		if (name in ci_files) or (name in ci_config_dir and ';'+ci_config_dir[name] in search(hash, 'tree')):
			ci = True
			break
	return ci

# df218f99b872ef59fd51952709c00903545cbb3f ex. CI commit hash

# checking whether the user provided the author
if len(sys.argv) > 1:
	author = sys.argv[1]
else:
	sys.exit('No author provided')

# getting the author's commits
proc = subprocess.Popen('echo "'+ author + '" | ~/lookup/getValues a2c', stdout=subprocess.PIPE, shell=True)
(out, err) = proc.communicate()
commits = [x for x in out.strip().split(';')[1:]]

# using a dictionary that has the commits' hashes as keys, so as to not search multiple times for the same commit
checked = {}

# for every commit, we look up whether the author included a CI file that did not exist in the parent commit
for commit in commits:
	print commit,
	tree_hash, parent_commit_hash = search(commit, 'commit')
	if tree_hash not in checked:
		checked[tree_hash] = ci_lookup(tree_hash)
	
	# controlling for the case of multiple parent commits
	all_parent_CI = False
	for parent in parent_commit_hash.split(':'):
		# controlling for the case of no parent commits
		if parent == '':
			break

		parent_tree_hash, _ = search(parent, 'commit')

		if parent_tree_hash not in checked:
			parent_CI = ci_lookup(parent_tree_hash)
			checked[parent_tree_hash] = parent_CI
		else:
			parent_CI = checked[parent_tree_hash]
		
		# checking all the parent commits for the usage of CI
		all_parent_CI = all_parent_CI or parent_CI
	print checked[tree_hash] and not all_parent_CI

print (time.time()-start_time)/len(commits), 'seconds per commit'

