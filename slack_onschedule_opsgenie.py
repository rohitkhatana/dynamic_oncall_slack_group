import requests, json

config = {}
with open('.env', 'r') as f:
    config = json.load(f)
    required_keys = set(['opsgenie_key', 'slack_auth_token'])
    if not set(config.keys()).issubset(required_keys):
        raise ValueError('opsgenie_key, slack_auth_token keys are required')

class Slack:

    def __init__(self):
        self._slack_base_url = 'https://slack.com/api'
        self._headers = {'Authorization': 'Bearer {}'.format(config.get('slack_auth_token'))}
        self._slack_cache_file = 'data/cache_slack_data.json'

    def __get_all_from_cache(self):
        try:
            file_data = open(self._slack_cache_file, 'r')
            slack_emails_id = json.load(file_data)
            print('file data--->', slack_emails_id)
            file_data.close()
            return slack_emails_id
        except:
            return {}

    def __get_from_cache(self, email):
        return self.__get_all_from_cache().get('users', {}).get(email, None)

    def __set_slack_id_into_cache(self, email, slack_user_id):
        print('slack_user_id', slack_user_id)
        slack_cache_data = self.__get_all_from_cache()
        if 'users' not in slack_cache_data:
            slack_cache_data['users'] = {}
        slack_cache_data['users'][email] = slack_user_id
        print(slack_cache_data)
        with open(self._slack_cache_file, 'w', encoding='utf-8') as f:
            json.dump(slack_cache_data, f, ensure_ascii=False, indent=4)


    def get_user_slack_id_by_email(self, email):
        slack_user_id = self.__get_from_cache(email)
        if slack_user_id:
            return slack_user_id
        print('cache miss for user id, calling slack api')
        endpoint = self._slack_base_url + '/users.lookupByEmail'
        params = {'email': email}
        response = requests.get(endpoint, headers=self._headers, params=params)
        slack_user_id = response.json().get('user').get('id')
        self.__set_slack_id_into_cache(email, slack_user_id)
        return slack_user_id

    def create_update_slack_group(self, opsgenie_on_call_users):
        endpoint = self._slack_base_url + '/usergroups.create'
        #no safe checking 
        opsgenie_team_name = opsgenie_on_call_users.get('_parent', {}).get('name')
        team_name = opsgenie_team_name.replace('_schedule', '').replace(' ', '-')
        group_name = 'oncall-{}'.format(team_name)
        params = {'name': group_name}
        print('params', params)

        response = requests.post(endpoint, headers=self._headers, json=params)
        user_group_info = response.json()
        if(user_group_info.get('error', None) == 'name_already_exists'):
            #modify_user_group
            pass
        else:
            #add users to group
            pass
        print(response.json(), response)


class Opsgenie:

    def __init__(self):
        #can be read from config
        self._opsgenie_base_url = 'https://api.opsgenie.com/v2'
        self._headers = {'Authorization': config.get('opsgenie_key')}
        self.slack = Slack()

    def __oncall(self, schedule_id):
        endpoint = self._opsgenie_base_url + '/schedules/{}/on-calls'.format(schedule_id)
        response = requests.get(endpoint, headers=self._headers)
        return response.json()

    def __get_schedules(self):
        endpoint = self._opsgenie_base_url + '/schedules'
        response = requests.get(endpoint, headers=self._headers)
        return response.json()

    def __participant_user_exists(self, participants):
        return filter(lambda participant: participant['type'] == 'user', participants)

    def __get_oncall_users(self, on_call_participants):
        print('__getoncallusers', on_call_participants)
        if self.__participant_user_exists(on_call_participants['onCallParticipants']):
            return on_call_participants
        else:
            None

    def get_oncalls(self):
        for schedule_id in self.get_schedule_ids():
            oncalls = self.__oncall(schedule_id)
            participant_users = self.__get_oncall_users(oncalls['data'])
            if self.__get_oncall_users(participant_users):
                self.slack.create_update_slack_group(participant_users)


    def get_schedule_ids(self):
        return list(map(lambda schedule: schedule['id'], self.__get_schedules()['data']))



s = Slack()
s.get_user_slack_id_by_email('rohit.khatana@qoala.id')
#s.create_update_slack_group('')
#o = Opsgenie()
#print(o.get_oncalls())
