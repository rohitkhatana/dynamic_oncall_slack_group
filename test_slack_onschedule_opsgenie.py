import json
import slack_onschedule_opsgenie as module

def read_test_data_file():
    try:
        test_file = "test/test_data.json"
        file_data = open(test_file, "r")
        test_cases = json.load(file_data)
        file_data.close()
        return test_cases
    except:
        return []

def construct_opsgenie_test_response(test_data):
    oncall_participants = test_data.get("emails")
    participants = []
    for participant in oncall_participants:
        participants.append({
            "name": participant
        })
    return {
        "_parent": {
            "name": "{}_schedule".format(test_data.get("name")),
        },
        "onCallParticipants": participants
    }

def test_update():
    s = module.Slack()
    test_cases = read_test_data_file()
    for test_case in test_cases:
        opsgenie_response = construct_opsgenie_test_response(test_case)
        print(opsgenie_response)
        s.create_update_slack_group(opsgenie_response)

if __name__ == "__main__":
    test_update()
