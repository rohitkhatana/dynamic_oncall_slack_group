import requests, json, os

zenduty_key = os.environ.get('zenduty_key')
slack_auth_token = os.environ.get('slack_auth_token')

required_keys = set(['zenduty_key', 'slack_auth_token'])

'''
!!IMPORTANT!! Do not give DEFAULT name to your schedules, this script will ignore the DEFAULT 
schedule name because Default schedule is used for admin team for which we do not want to create oncall slack group
'''


class Slack:

    def __init__(self):
        self._slack_base_url = 'https://slack.com/api'
        self._headers = {'Authorization': 'Bearer {}'.format(slack_auth_token)}
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

    def __get_user_id_from_cache(self, email):
        return self.__get_all_from_cache().get('users', {}).get(email, None)

    def __set_group_id_into_cache(self, group_name, group_id) :
        slack_cache_data = self.__get_all_from_cache()
        if 'usergroups' not in slack_cache_data:
            slack_cache_data['usergroups'] = {}
        print('---settingup---', slack_cache_data)
        slack_cache_data['usergroups'][group_name] = group_id
        print(slack_cache_data)
        # with open(self._slack_cache_file, 'w', encoding='utf-8') as f:
        #     json.dump(slack_cache_data, f, ensure_ascii=False, indent=4)

    def __set_slack_id_into_cache(self, email, slack_user_id):
        print('slack_user_id', slack_user_id)
        slack_cache_data = self.__get_all_from_cache()
        if 'users' not in slack_cache_data:
            slack_cache_data['users'] = {}
        slack_cache_data['users'][email] = slack_user_id
        print(slack_cache_data)
        # with open(self._slack_cache_file, 'w', encoding='utf-8') as f:
        #     json.dump(slack_cache_data, f, ensure_ascii=False, indent=4)

    def __get_group_id_from_cache(self, group_name):
        return self.__get_all_from_cache().get('usergroups', {}).get(group_name, None)


    def get_user_slack_id_by_email(self, email):
        slack_user_id = self.__get_user_id_from_cache(email)
        if slack_user_id:
            return slack_user_id
        print('cache miss for user id, calling slack api')
        endpoint = self._slack_base_url + '/users.lookupByEmail'
        params = {'email': email}
        response = requests.get(endpoint, headers=self._headers, params=params)
        # print('response--->', response.json())
        slack_user_id = response.json().get('user').get('id')
        self.__set_slack_id_into_cache(email, slack_user_id)
        return slack_user_id

    def __filter_group_id_by_name(self, slack_api_data, group_name):
        slack_group = list(filter(lambda x: x.get('name').lower() == group_name.lower(), slack_api_data))
        if not slack_group:
            return None
        else:
            print('filter--->',slack_group)
            return slack_group[0].get('id')

    def __slack_group_id(self, group_name):
        create_endpoint = self._slack_base_url + '/usergroups.create'
        params = {'name': group_name, 'handle': group_name.lower()}
        response = requests.post(create_endpoint, headers=self._headers, json=params)
        user_group_info = response.json()
        print('usercreate group--->', user_group_info)
        if(user_group_info.get('error', None) == 'name_already_exists'):
            get_group_list_endpoint = self._slack_base_url + '/usergroups.list'
            group_list_response = requests.get(get_group_list_endpoint, headers=self._headers)
            usergroups_from_slack = group_list_response.json().get('usergroups')
            group_id = self.__filter_group_id_by_name(usergroups_from_slack, group_name)
            return group_id
        else:
            return user_group_info.get('usergroup').get('id')

    def create_update_slack_group(self, zenduty_on_call_users):
        #no safe checking 
        zenduty_team_name = zenduty_on_call_users.get('name')
        on_call_participants = zenduty_on_call_users.get('onCallParticipants', [])
        team_name = zenduty_team_name.replace(' schedule', '').replace(' ', '-')
        group_name = 'oncall-{}'.format(team_name)
        print('group_name-->', group_name)
        usergroup_id = self.__get_group_id_from_cache(group_name)
        if usergroup_id:
            print('group id exists in cache', usergroup_id)
        else:
            print('creating new user group with name: {}'.format(group_name))
            print(group_name)
            usergroup_id = self.__slack_group_id(group_name)
            self.__set_group_id_into_cache(group_name, usergroup_id)
            print('usergroup_id->', usergroup_id)
        self.__update_user_group(usergroup_id, on_call_participants)

    def __update_user_group(self, usergroup_id, on_call_participants):
        slack_user_ids = []
        for participant in on_call_participants:
            slack_user_id = self.get_user_slack_id_by_email(participant['name'])
            slack_user_ids.append(slack_user_id)
        update_endpoint = self._slack_base_url + '/usergroups.users.update'
        params = {
            'usergroup': usergroup_id,
            'users':slack_user_ids
        }
        response = requests.post(update_endpoint, headers=self._headers, json=params)
        update_response = response.json()
        return None


class Zenduty:

    def __init__(self):
        #can be read from config
        self._zenduty_base_url = 'https://www.zenduty.com/api/account'
        self._headers = {'Authorization':"token {}".format(zenduty_key)}
        self.slack = Slack()

    def __oncall(self, team_id,schedule_id):
        endpoint = self._zenduty_base_url + '/teams/{}/schedules/{}/get_on_call/'.format(team_id,schedule_id)
        response = requests.get(endpoint, headers=self._headers)
        return response.json()

    def __get_schedules(self):
        teams = self._zenduty_base_url + '/teams'
        response_teams = requests.get(teams, headers=self._headers)
        response_teams_json = response_teams.json()
        schedules = []
        for team in response_teams_json:
            endpoint = "{}/teams/{}/schedules".format(self._zenduty_base_url, team['unique_id'])
            response = requests.get(endpoint, headers=self._headers)
            schedules.extend(response.json())
        return list(filter(lambda s: s.get('name') != 'Default', schedules))

    def get_oncalls(self):
        for schedule in self.__get_schedules():
            if schedule.get('name') != 'Default':
                oncalls = self.__oncall(schedule["team"],schedule["unique_id"])
                participants = []
                for i in oncalls:
                    try:
                        participants.append({"id":i["username"],"name":i["email"]})
                    except:
                        pass
                schedule = {"name":schedule["name"],"onCallParticipants":participants}
                self.slack.create_update_slack_group(schedule)



s = Slack()
z = Zenduty()
z.get_oncalls()
def lambda_handler(event, context):
    print(z.get_oncalls())
    return {
        'statusCode': 200,
        'body': json.dumps('Success!')
    }

