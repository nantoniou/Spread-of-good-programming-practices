import sys
import os
sys.path.insert(0, '../oscar.py')

from oscar import Project
import subprocess

"""
Process used to search for a specific blob, commit or tree.
"""
def search(hash, type):
	proc = subprocess.Popen('echo ' + hash + ' | ~/lookup/showCnt ' + type, stdout=subprocess.PIPE, shell=True)
	(out, err) = proc.communicate()
	return out

splitted_commit = search('0aea9614e05b94316380a29089a3c5a84d1232a1', 'commit').split()
# the corresponding hash of the tree from a commit is always the second word
tree_hash = splitted_commit[1]

tree = search(tree_hash, 'tree')

# split the result into its components (blobs and directories) and then separate the mode, the hash and the name
blobs = [blob.split(';') for blob in tree.split()]

index = {'mode':1, 'hash':1, 'name':2}

# files used in continuous integration
ci_files = ['.gitlab-ci.yml', '.travis.yml', 'Jenkinsfile', 'buddy.yml', '.drone.yml', 'circle.yml', 'bamboo.yaml', 'codeship-steps.yml']

# some tools use generic names for the configuration files, placing them in a distinct folder
ci_config_folders = {'.circleci':'config.yml'}


ci = False

for blob in blobs:
	name = blob[index['name']]
	hash = blob[index['hash']]
	if (name in ci_files) or (name in ci_config_folders and ';'+ci_config_folders[name]+'\n' in search(hash, 'tree')):
		print name, search(hash, 'tree')
		ci = True
		break
print 'CI = ', ci

