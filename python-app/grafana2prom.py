#!/bin/python3

import requests
import time
import os
import logging
import argparse

from math import ceil
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge

class SonarQubeAPI:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.auth = (self.token, '')

    def get_project_from_page(self, page):
        response = requests.get(f'{self.url}/api/components/search?ps=500&qualifiers=TRK&p={page}', auth=self.auth, verify=cert_file)
        return response.json()

    def get_project_list(self):
        response = requests.get(f'{self.url}/api/components/search?ps=500&qualifiers=TRK', auth=self.auth, verify=cert_file)
        page_number = ceil(response.json()['paging']['total']/response.json()['paging']['pageSize'])
        response = response.json()['components']
        if page_number > 1 :
            for i in range(2, page_number+1):
                response.extend(self.get_project_from_page(i)['components'])
        return response
    
    def get_project_branch_list(self, project_key):
        response = requests.get(f'{self.url}/api/project_branches/list?project={project_key}', auth=self.auth, verify=cert_file)
        return response.json()['branches']
    
    def get_project_banch_issues(self, project_key, branch):
        response = requests.get(f'{self.url}/api/issues/search?componentKeys={project_key}&branch={branch}', auth=self.auth, verify=cert_file)
        return response.json()

    def check_connection(self):
       try:
           response = requests.get(f'{self.url}/api/system/status', auth=self.auth, verify=cert_file)
           response.raise_for_status()
           return True
       except requests.exceptions.RequestException as err:
           logging.debug(f"Error: {err}")
           return False
       
    def check_authentication(self):
        try:
            response = requests.get(f'{self.url}/api/user_tokens/search', auth=self.auth, verify=cert_file)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            logging.debug(f"Error: {err}")
            return False

def sonar_error_gauge(project_list):
    for project in project_list:
        project_key = project['key']
        project_name = project['name']
        project_branchs = sonar.get_project_branch_list(project_key)
        for project_branch in project_branchs :
            project_branch_name = project_branch['name']
            project_issues = sonar.get_project_banch_issues(project_key, project_branch_name)
            sonarqube_project_errors_total.labels(project_key=project_key, project_name=project_name, project_branch_name=project_branch_name).set(project_issues['total'])
            blocker_count = sum(1 for issue in project_issues['issues'] if issue['severity'] == 'BLOCKER')
            sonarqube_project_errors_blocker.labels(project_key=project_key, project_name=project_name, project_branch_name=project_branch_name).set(blocker_count)

#Retreive arguments given while starting the script
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Prometheus collector for a sonarqube server')
parser.add_argument(
    "--verbose",
    "-v",
    required=False,
    help="increase output verbosity",
    action="store_true")
args = parser.parse_args()

#Set logging level
if args.verbose:
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.captureWarnings(True)
else:
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    

#Load values from .env file
load_dotenv()
sonar_key = os.getenv('SONAR_KEY')
sonar_url = os.getenv('SONAR_URL')
filter = os.getenv('FILTER')
cert_file = os.getenv('CERT_FILE')
http_port = int(os.getenv('HTTP_PORT'))
max_projects = int(os.getenv('MAX_PROJECTS'))

#Create Sonar and connect to Sonarqube
sonar = SonarQubeAPI(sonar_url, sonar_key)

# Check connection to SonarQube API
logging.debug('Check connection to SonarQube API.')
error_connect_compt = 1
while not sonar.check_connection():
    if error_connect_compt > 4 :
        logging.critical("Unable to connect to SonarQube API. Please check your connection or configuration.")
        exit(1)
    logging.error(f'Unable to connect to SonarQube API on try {error_connect_compt}. Retrying in 5 seconds...')
    error_connect_compt +=1
    time.sleep(5)
logging.debug('Connection to SonarQube API established.')


# Check authentication to SonarQube API
logging.debug('Check authentification to SonarQube API')
while not sonar.check_authentication():
    logging.critical("Unable to authenticate to SonarQube API. Please check your token.")
    exit(1)
logging.debug('Authentification to SonarQube API done.')


#Create the Prometheus gauge
sonarqube_project_errors_total = Gauge('sonarqube_project_errors_total', 'SonarQube project errors', ['project_key', 'project_name', 'project_branch_name'])
sonarqube_project_errors_blocker = Gauge('sonarqube_project_errors_blocker', 'SonarQube project errors blocker', ['project_key', 'project_name', 'project_branch_name'])

# Start up the server to expose the metrics.
logging.info(f'Start http server on port {http_port}')
start_http_server(http_port)
while True:
    logging.debug('Genrating project list')
    project_list = sonar.get_project_list()
    logging.debug('Filtering project list')
    project_list = [i for i in project_list if filter in i['key']]
    if len(project_list) > max_projects:
        logging.critical(f'Too many projects ({len(project_list)}), risk of overloading SonarQube !\nBy default max 100 projects, can be update in .env file.')
        exit(1)
    sonar_error_gauge(project_list)
    logging.info('All done, waiting 1h before next scrape.')
    time.sleep(3600)
    