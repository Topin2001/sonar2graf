#!/bin/python3

import requests
from prometheus_client import start_http_server, Gauge
import time
import os
from dotenv import load_dotenv

class SonarQubeAPI:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.auth = (self.token, '')

    def get_project_info(self, project_key):
        response = requests.get(f'{self.url}/api/project_analyses/search?project={project_key}', auth=self.auth)
        return response.json()
    
    def get_project_list(self):
        response = requests.get(f'{self.url}/api/projects/search', auth=self.auth)
        return response.json()
    
    def get_project_issues(self, project_key):
        response = requests.get(f'{self.url}/api/issues/search?componentKeys={project_key}', auth=self.auth)
        return response.json()
    
    def check_connection(self):
       try:
           response = requests.get(f'{self.url}/api/system/status', auth=self.auth)
           response.raise_for_status()
           return True
       except requests.exceptions.RequestException as err:
           print(f"Error: {err}")
           return False
       
    def check_authentication(self):
        try:
            response = requests.get(f'{self.url}/api/user_tokens/search', auth=self.auth)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            print(f"Error: {err}")
            return False

load_dotenv()

sonar_key = os.getenv('SONAR_KEY')
sonar_url = os.getenv('SONAR_URL')
http_port = int(os.getenv('HTTP_PORT'))

sonar = SonarQubeAPI(sonar_url, sonar_key) #Mettre l'adresse IP du server sonarqube


# Check connection to SonarQube API
while not sonar.check_connection():
    print("Unable to connect to SonarQube API. Retrying in 5 seconds...")
    time.sleep(5)

# Check authentication to SonarQube API
while not sonar.check_authentication():
    print("Unable to authenticate to SonarQube API. Please check your token.")
    exit(1)


sonarqube_project_errors_total = Gauge('sonarqube_project_errors_total', 'SonarQube project errors', ['project_key', 'project_name', 'project_last_analysis'])
sonarqube_project_errors_blocker = Gauge('sonarqube_project_errors_blocker', 'SonarQube project errors blocker', ['project_key', 'project_name', 'project_last_analysis'])

def sonar_error_gauge(project_list):
    for project in project_list['components']:
        project_key = project['key']
        project_name = project['name']
        project_last_analysis = project['lastAnalysisDate']
        project_issues = sonar.get_project_issues(project_key)
        sonarqube_project_errors_total.labels(project_key=project_key, project_name=project_name, project_last_analysis=project_last_analysis).set(project_issues['total'])

def sonar_blocker_gauge(project_list):
    for project in project_list['components']:
        project_key = project['key']
        project_name = project['name']
        project_last_analysis = project['lastAnalysisDate']
        project_issues = sonar.get_project_issues(project_key)
        blocker_count = sum(1 for issue in project_issues['issues'] if issue['severity'] == 'BLOCKER')
        sonarqube_project_errors_blocker.labels(project_key=project_key, project_name=project_name, project_last_analysis=project_last_analysis).set(blocker_count)


# Start up the server to expose the metrics.
start_http_server(http_port)
while True:
    project_list = sonar.get_project_list()
    sonar_error_gauge(project_list)
    sonar_blocker_gauge(project_list)
    
    time.sleep(15)
    