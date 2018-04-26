'''
    TO DO:
        - error checking on authenticate()
        - I'm not sure if I have to do the full authentication thing if a token
          expires or if there's a simple token refresh process
'''

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


#  HELPER FUNCTIONS
def save(settings):
    ''' Save user settings to file. '''

    with open(user_settings, 'wb') as f:
        pickle.dump(settings, f)


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

    params = {'method':'rtm.auth.getFrob', 'api_key':API_KEY, 'format':'json'}

    # create signature from existing params and add as parameter
    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)

    if r.status_code != 200:
        raise Exception("Error ({}) connecting to Remember the Milk. Please "
                        "try again later.".format(r.status_code))

    frob = r.json()['rsp']['frob']

    return frob


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

    r_authentication = requests.get(auth_url, params=params)

    click.echo('')
    click.echo('Open the following link in your browser in order to approve authentication '
        'from Remember the Milk:')
    click.echo('')
    click.echo(r_authentication.url)

    # pause the application while the user approves authentication
    value = click.prompt('Type "c" and then press enter to continue.')

    # now get the authentication token
    params = {'api_key':API_KEY,
              'method':'rtm.auth.getToken',
              'format':'json',
              'frob':frob}
    # sign every request
    params['api_sig'] = make_api_sig(params)

    r_token = requests.get(methods_url, params=params)

    #r_token.json()
    settings['token'] = r_token.json()['rsp']['auth']['token']
    settings['username'] = r_token.json()['rsp']['auth']['user']['username']
    settings['name'] = r_token.json()['rsp']['auth']['user']['fullname']
    save(settings)

    click.echo('Congrats, {}, it worked!'.format(settings['name']))

    return


def check_token():
    ''' Check user token. Do nothing, refresh token, or authenticate. '''

    if settings['token']:
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


@click.group()
def main():
    pass


@main.command()
def test():
    check_token()
    click.echo('Hello {}!'.format(settings['name']))


@main.command()
def get_completed_tasks():
    check_token()
    click.echo('Token good.')
    params = {'method':'rtm.tasks.getList',
              'api_key':API_KEY,
              'format':'json',
              'auth_token':settings['token'],
              'filter':'completed:today'}
    params['api_sig'] = make_api_sig(params)

    r = requests.get(methods_url, params=params)

    print(r.json()['rsp']['tasks'])


@main.command()
@click.argument('out', type=click.File('w'), default='-')
@click.option('--format', type=str, help="File format.")
def talk(out, format):
    """Command line interface for Remember the Milk."""
    click.echo('Hello {}!'.format(settings['username']))

if __name__ == "__main__":
    main()
