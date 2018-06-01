#!/python3

'''
    TO DO:
        - use click.secho() instead of print() in tasks()
        - order tasks retrieved by due date, no due date at end
        - get other task attributes (attachments, assigned, ?)
        - get subtasks (recurvisely because subtasks can have subtasks)
        - I'm not sure if I have to do the full authentication thing if a token
          expires or if there's a simple token refresh process
'''

import sys
import datetime
import click
import requests
import hashlib
import pickle
from config import API_KEY, SHARED_SECRET


auth_url = 'https://www.rememberthemilk.com/services/auth/'
methods_url = 'https://api.rememberthemilk.com/services/rest/'

user_settings = 'user.pickle'

# load settings from user_settings, create both file and data object if necessary
try:
    with open(user_settings, 'rb') as f:
        settings = pickle.load(f)
except FileNotFoundError:
    with open(user_settings, 'wb') as f:
        settings = {}
except EOFError:
    settings = {}


class BadResponseException(Exception):
    pass

class NoTasksException(Exception):
    pass

class NoListException(Exception):
    pass


################################################################################
# CLASSES
################################################################################
class Task:

    def __init__(self, taskseries, task):
        self.id = taskseries['id']
        self.name = taskseries['name']
        self.url = taskseries['url'] if 'url' in taskseries else ''
        self.due = task['due'] if 'due' in task else ''
        self.priority = '' if task['priority'] == 'N' else task['priority']

        self.tags = []
        if 'tag' in taskseries['tags']:
            for tag in taskseries['tags']['tag']:
                self.tags.append(tag)

        self.notes = []
        if 'note' in taskseries['notes']:
            for note in taskseries['notes']['note']:
                self.notes.append(note['$t'])

        self.participants = []
        if 'contact' in taskseries['participants']:
            for participant in taskseries['participants']['contact']:
                self.participants.append(participant['fullname'])


################################################################################
#  HELPER FUNCTIONS
################################################################################
def save(settings):
    ''' Save user settings to file. '''

    with open(user_settings, 'wb') as f:
        pickle.dump(settings, f)


def get_data_or_exit(response):
    ''' Return response object or exit if response was failure.'''

    data = response.json()['rsp']

    if data['stat'] != 'ok':
        click.secho("An error occured while retrieving data from RTM. {}: {}" \
                .format({data['err']['code']}, {data['err']['msg']}), fg='red')
        sys.exit(1)

    return data


def make_api_sig(params):
    '''
    Creates an API signature as required by RTM. See
    https://www.rememberthemilk.com/services/api/authentication.rtm

    This creates a string consisting of the SHARED SECRET provided by RTM concatenated
    with the sorted key/value pairs of the parameters to be sent. This api_sig
    then becomes another parameter sent with the request to RTM.
    '''

    api_sig = SHARED_SECRET + ''.join('{}{}'.format(key, value) for key, value in sorted(params.items()))
    api_sig = hashlib.md5(api_sig.encode('utf-8'))
    return api_sig.hexdigest()


def get_frob():
    ''' Returns *frob*. Part of the authentication process.'''

    params = {'method':'rtm.auth.getFrob',
              'api_key':API_KEY,
              'format':'json'}
    # create signature from existing params and add as parameter
    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)

    if r.status_code != 200:
        click.secho("Error ({}) connecting to Remember the Milk. Please " \
                        "try again later.".format(r.status_code), fg='red')
        sys.exit(1)

    return data['frob']


def authenticate():
    '''
    Authenticates user to RTM and stores token to *user_settings* file.

    See https://www.rememberthemilk.com/services/api/authentication.rtm.
    '''

    frob = get_frob()
    params = {'api_key':API_KEY,
              'frob':frob,
              'perms':'read'}
    params['api_sig'] = make_api_sig(params)

    r = requests.get(auth_url, params=params)

    if r.status_code != 200:
        click.secho("Error ({}) connecting to Remember the Milk. Please "
                        "try again later.".format(r.status_code), fg='red')
        sys.exit(1)

    click.echo('')
    click.echo('Open the following link in your browser in order to approve authentication '
        'from Remember the Milk:')
    click.echo('')
    click.echo(r.url)

    # pause the application while the user approves authentication
    value = click.prompt('Type "c" and then press enter to continue.')

    # now get the authentication token
    params = {'api_key':API_KEY,
              'method':'rtm.auth.getToken',
              'format':'json',
              'frob':frob}

    # sign every request
    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)

    r = r.json()['rsp']
    settings['token'] = r['auth']['token']
    settings['username'] = r['auth']['user']['username']
    settings['name'] = r['auth']['user']['fullname']
    save(settings)

    click.echo('Congrats, {}, it worked!'.format(settings['name']))

    return


def check_token():
    ''' Check user token. Do nothing, refresh token, or authenticate. '''

    if 'token' in settings:
        params = {'api_key':API_KEY,
                  'method': 'rtm.auth.checkToken',
                  'format':'json',
                  'auth_token':settings['token']}
        params['api_sig'] = make_api_sig(params)

        r = requests.get(methods_url, params=params)

        if r.status_code != 200:
            click.secho("Error ({}) connecting to Remember the Milk. Please "
                            "try again later.".format(r.status_code), fg='red')
            sys.exit(1)

        r = r.json()['rsp']

        if r['stat'] != 'ok':
            click.echo("There's been an error.")
            click.echo('{}: {}'.format({r['err']['code']}, {r['err']['msg']}))
            click.echo('Attempting to reauthenticate...')
            authenticate()

    else:
        authenticate()

    return


def get_lists():
    """ Get all of the user's lists."""

    check_token()
    params = {'api_key':API_KEY,
              'method':'rtm.lists.getList',
              'format':'json',
              'auth_token':settings['token']}

    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)

    return get_data_or_exit(r)['lists']['list']


def get_tasks(list_name='', tag='', status=''):
    ''' Get user tasks by various attributes.

    Inputs:
        -list_name: name of list_name
        -tag: name of tag
        -status : completed or incomplete
    '''

    check_token()
    params = {'api_key':API_KEY,
              'method':'rtm.tasks.getList',
              'format':'json',
              'auth_token':settings['token']}

    if list_name:
        rtm_lists = get_lists()

        list_id = ''
        for rtm_list in rtm_lists:
            if list_name == rtm_list['name']:
                list_id = rtm_list['id']

        if not list_id:
            raise NoListException

        params['list_id'] = list_id

    if status == 'completed':
        # figure out x days ago date
        #since = datetime.date.today() - datetime.timedelta(days=days)
        #params['filter'] = 'completedAfter:' + str(since)
        params['filter'] = 'status:completed'

    if status == 'incomplete':
        params['filter'] = 'status:incompleted'

    # if tag included, will have find tasks for that tag later because
    # the query can take only one params['filter'] parameter

    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)
    rtm_tasks = get_data_or_exit(r)['tasks']

    tasks = []

    if 'list' not in rtm_tasks:
        raise NoTasksException

    for rtm_list in rtm_tasks['list']:
        if 'taskseries' in rtm_list:
            for taskseries in rtm_list['taskseries']:
                if tag:
                    if 'tag' in taskseries['tags']:
                        for task in taskseries['task']:
                            if tag in taskseries['tags']['tag']:
                                tasks.append(Task(taskseries, task))
                else:
                    for task in taskseries['task']:
                        tasks.append(Task(taskseries, task))
    if not tasks:
        raise NoTasksException

    return tasks


################################################################################
# commands
################################################################################
@click.group()
def main():
    """Don't Forget the Python: command-line interface for Remember the Milk.

    Type "<command> --help" to see options and additional info."""


@main.command()
def greet():
    '''Hello.'''
    check_token()
    click.echo('Hello {}!'.format(settings['name']))


@main.command()
@click.option('--archived', is_flag=True, help="Show archived lists.")
@click.option('--smart', is_flag=True, help="Show smart lists.")
@click.option('--all', is_flag=True, help="Show all lists.")
def lists(archived, smart, all):
    '''List your lists!'''

    rtm_lists = get_lists()

    sub_list = []

    for rtm_list in rtm_lists:
        if all:
            sub_list.append(rtm_list)
        else:
            if archived and smart:
                if rtm_list['smart'] == '1' and rtm_list['archived'] == '1':
                    sub_list.append(rtm_list)
            elif archived and not smart:
                if rtm_list['smart'] == '0' and rtm_list['archived'] == '1':
                    sub_list.append(rtm_list)
            elif not archived and smart:
                if rtm_list['smart'] == '1' and rtm_list['archived'] == '0':
                    sub_list.append(rtm_list)
            else:
                if rtm_list['smart'] == '0' and rtm_list['archived'] == '0':
                    sub_list.append(rtm_list)

    if not sub_list:
        click.secho('No lists to show.', fg='red')
    else:
        for rtm_list in sorted(sub_list, key=lambda k: k['name'].lower()):
            click.echo(rtm_list['name'])
    return


@main.command()
@click.option('--list_name', '-l', default='', help="Tasks from a particular list.")
@click.option('--tag', '-t', default='', help="Tasks with a particular tag.")
@click.option('--incomplete', '-i', 'status', flag_value='incomplete', help="Incomplete tasks only.")
@click.option('--completed', '-c', 'status', flag_value='completed', help="Completed tasks only.")
#@click.option('--days', -'d', default=0, help="For completed tasks, number of days since completed.")
@click.option('--verbose', '-v', is_flag=True, help="Include tags and notes.")
def tasks(list_name, tag, status, verbose):
    """List your tasks."""

    try:
        tasks = get_tasks(list_name, tag, status)
    except NoTasksException:
        click.secho("No tasks found with those parameters.", fg='red')
        return
    except NoListException:
        click.secho('No list by that name found.', fg='red')
        return

    for task in tasks:
        print(task.name, end='')
        if task.due:
            print(' (due: ' + task.due +')')
        else:
            print('')
        if verbose:
            if task.tags:
                print(' tags: ', end='')
                for tag in task.tags:
                    print(tag, end=', ')
                print('')
            if task.notes:
                for note in task.notes:
                    print(' note: ' + note)
            if task.url:
                print(' url: ' + task.url)
            if task.priority:
                print(' priority: ' + task.priority)
            if task.participants:
                for participant in task.participants:
                    print(' participant: ' + participant)
            print('')

    return


@main.command()
@click.option('--list_name', '-l', default='', help="List name.")
@click.option('--incomplete', '-i', 'status', flag_value='incomplete', help="Incomplete tasks only.")
@click.option('--completed', '-c', 'status', flag_value='completed', help="Completed tasks only.")
@click.option('--days', '-d', default=0, help="For completed tasks, number of days since completed.")
def export(list_name, status):
    """Export tasks to pdf."""

    tasks = get_tasks(list_name, status)

    # for task in tasks:


if __name__ == "__main__":
    main()
