#!/bin/python3

import requests
import time
import os
import urllib3

from math import ceil
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge

class SonarQubeAPI:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.auth = (self.token, '')

    def get_project_from_page(self, page):
        response = requests.get(f'{self.url}/api/components/search?ps=500&qualifiers=TRK&p={page}', auth=self.auth, verify=False)
        return response.json()

    def get_project_list(self):
        response = requests.get(f'{self.url}/api/components/search?ps=500&qualifiers=TRK', auth=self.auth, verify=False)
        page_number = ceil(response.json()['paging']['total']/response.json()['paging']['pageSize'])
        response = response.json()['components']
        if page_number > 1 :
            for i in range(2, page_number+1):
                response.extend(self.get_project_from_page(i)['components'])
        return response
    
    def get_project_issues(self, project_key):
        response = requests.get(f'{self.url}/api/issues/search?componentKeys={project_key}', auth=self.auth, verify=False)
        return response.json()
    
    def check_connection(self):
       try:
           response = requests.get(f'{self.url}/api/system/status', auth=self.auth, verify=False)
           response.raise_for_status()
           return True
       except requests.exceptions.RequestException as err:
           print(f"Error: {err}")
           return False
       
    def check_authentication(self):
        try:
            response = requests.get(f'{self.url}/api/user_tokens/search', auth=self.auth, verify=False)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            print(f"Error: {err}")
            return False

urllib3.disable_warnings()
#Load values from .env file
load_dotenv()

sonar_key = os.getenv('SONAR_KEY')
sonar_url = os.getenv('SONAR_URL')
filter = os.getenv('FILTER')
http_port = int(os.getenv('HTTP_PORT'))
max_projects = int(os.getenv('MAX_PROJECTS'))

#Create Sonar and connect to Sonarqube
sonar = SonarQubeAPI(sonar_url, sonar_key)

# Check connection to SonarQube API
while not sonar.check_connection():
    print("Unable to connect to SonarQube API. Retrying in 5 seconds...")
    time.sleep(5)

# Check authentication to SonarQube API
while not sonar.check_authentication():
    print("Unable to authenticate to SonarQube API. Please check your token.")
    exit(1)


sonarqube_project_errors_total = Gauge('sonarqube_project_errors_total', 'SonarQube project errors', ['project_key', 'project_name'])
sonarqube_project_errors_blocker = Gauge('sonarqube_project_errors_blocker', 'SonarQube project errors blocker', ['project_key', 'project_name'])

def sonar_error_gauge(project_list):
    for project in project_list:
        project_key = project['key']
        project_name = project['name']
        project_issues = sonar.get_project_issues(project_key)
        sonarqube_project_errors_total.labels(project_key=project_key, project_name=project_name).set(project_issues['total'])
        blocker_count = sum(1 for issue in project_issues['issues'] if issue['severity'] == 'BLOCKER')
        sonarqube_project_errors_blocker.labels(project_key=project_key, project_name=project_name).set(blocker_count)


# Start up the server to expose the metrics.
start_http_server(http_port)
while True:
    project_list = sonar.get_project_list()
    project_list = [i for i in project_list if filter in i['key']]
    if len(project_list) > max_projects:
        print('Too many projects, risk of overloading SonarQube !\nBy default max 100 projects, can be update in .env file.')
        exit(1)
    sonar_error_gauge(project_list)
    time.sleep(3600)
    