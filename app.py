'''
    TO DO:
        - I'm not sure if I have to do the full authentication thing if a token
          expires or if there's a simple token refresh process
        - for lists(), it might be a good idea to first define a class and turn
          the lists into an object of that class, and return the list of objects.
          If the API changes, it will be easier to change the variable names in the
          class than to change them in the function (where they are repeated).
'''

import datetime
import click
import requests
import hashlib
import pickle
from icecream import ic
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


################################################################################
#  HELPER FUNCTIONS
################################################################################
def save(settings):
    ''' Save user settings to file. '''

    with open(user_settings, 'wb') as f:
        pickle.dump(settings, f)


def get_data_or_raise_exception(response):
    data = response.json()['rsp']

    if data['stat'] != 'ok':
        click.echo("There's been an error.")
        raise Exception('{}: {}'.format({data['err']['code']}, {data['err']['msg']}))

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
        raise Exception("Error ({}) connecting to Remember the Milk. Please "
                        "try again later.".format(r.status_code))

    data = get_data_or_raise_exception(r)

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
        raise Exception("Error ({}) connecting to Remember the Milk. Please "
                        "try again later.".format(r.status_code))

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
    #r_token.json()
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
            raise Exception("Error ({}) connecting to Remember the Milk. Please "
                            "try again later.".format(r.status_code))

        r = r.json()['rsp']

        if r['stat'] != 'ok':
            click.echo("There's been an error.")
            click.echo('{}: {}'.format({r['err']['code']}, {r['err']['msg']}))
            click.echo('Attempting to reauthenticate...')
            authenticate()

    else:
        authenticate()

    return


def tidy_task(everything):
    tasks = []
    for task_list in everything['list']:
        print('task_list id:', task_list['id'])
        for task in task_list['taskseries']:
            print('task name:', task['name'])

    return


################################################################################
# commands
################################################################################
@click.group()
def main():
    """Command line interface for Remember the Milk.

    Type "<command> --help" to see options and additional info."""


@main.command()
def test():
    check_token()
    click.echo('Hello {}!'.format(settings['name']))


@main.command()
@click.option('--archived', is_flag=True, help="Show archived lists.")
@click.option('--smart', is_flag=True, help="Show smart lists.")
@click.option('--all', is_flag=True, help="Show all lists.")
def lists(archived, smart, all):
    '''List your lists!'''
    check_token()
    params = {'api_key':API_KEY,
              'method':'rtm.lists.getList',
              'format':'json',
              'auth_token':settings['token']}

    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)
    lists = get_data_or_raise_exception(r)['lists']['list']

    lists_names = []

    for rtm_list in lists:
        if all:
            lists_names.append(rtm_list['name'])
        else:
            if archived and smart:
                if rtm_list['smart'] == '1' and rtm_list['archived'] == '1':
                    lists_names.append(rtm_list['name'])
            elif archived and not smart:
                if rtm_list['smart'] == '0' and rtm_list['archived'] == '1':
                    lists_names.append(rtm_list['name'])
            elif not archived and smart:
                if rtm_list['smart'] == '1' and rtm_list['archived'] == '0':
                    lists_names.append(rtm_list['name'])
            else:
                if rtm_list['smart'] == '0' and rtm_list['archived'] == '0':
                    lists_names.append(rtm_list['name'])

    if not lists_names:
        print('No lists to show.')
    else:
        for name in sorted(lists_names, key=lambda s: s.lower()):
            print(name)

    return


@main.command()
@click.option('--list_name', default='', help="Name of list from which to get tasks.")
@click.option('--days', default=30, help="Number of days to go back.")
def completed(list_name, days):
    check_token()
    params = {'api_key':API_KEY,
              'method':'rtm.tasks.getList',
              'format':'json',
              'auth_token':settings['token']}

    if list_name:
        params['filter'] = 'list:' + list_name

    if days:
        # figure out x days ago date
        since = datetime.date.today() - datetime.timedelta(days=days)
        params['filter'] = 'completedAfter:' + str(since)

    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)
    everything = get_data_or_raise_exception(r)['tasks']

    tasks = tidy_tasks(everything)

    return

'''
@main.command()
@click.argument('out', type=click.File('w'), default='-')
@click.option('--format', type=str, help="File format.")
def talk(out, format):
    """Command line interface for Remember the Milk."""
    click.echo('Hello {}!'.format(settings['username']))
'''

if __name__ == "__main__":
    main()
