#!python3

'''
    TO DO:
        - now: format date in display_tasks()
        - continue to develop tests (most immediately for display_tasks())
        - adjust authenticate() to have reauthenticate scenario
        - user.pickle gets saved (and I assume so does the exported file) in
          whatever directory the user runs the command from. Need to make it
          a specific file, probably hidden file under user home directory.
        - use click.secho() instead of print() in tasks()
        - get other task attributes (attachments, assigned, ?)
        - get subtasks (recurvisely because subtasks can have subtasks)
        - I'm not sure if I have to do the full authentication thing if a token
          expires or if there's a simple token refresh process
        - once Pillow is available for Python 3.7, upgrade to 3.7 and delete/re-install
          the virtual environment. That will enable me to make Task a dataclass.
'''

import sys
import datetime
import click
import requests
import hashlib
import textwrap
import pickle

from tabulate import tabulate

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors

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


class BadDataException(Exception):
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
        self.url = '' if not taskseries['url'] else taskseries['url']
        self.due = 'never' if not task['due'] else task['due']
        self.completed = task['completed']
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

    def convert_to_list(self):
        ''' Returns Task as list, with task name text wrapped.'''
        if self.completed:
            return ['\n'.join(textwrap.wrap(self.name, 50)), self.completed]
        else:
            return ['\n'.join(textwrap.wrap(self.name, 50)), self.due]


################################################################################
#  HELPER FUNCTIONS
################################################################################
def save(settings):
    ''' Save user settings to file. '''

    with open(user_settings, 'wb') as f:
        pickle.dump(settings, f)


def handle_response(r):
    ''' Deal with common responses from RTM API.
    This is where a user will first be authenticated (or reauthenticated if the
    authorization token expires).
    '''

    if r.status_code != 200:
        click.secho("Error ({}:{}) connecting to Remember the Milk. Please " \
                    "try again later.".format(r.status_code, r.reason), fg='red')
        sys.exit('Bad Status Code')
    else:
        data = r.json()['rsp']

        if data['stat'] != 'ok':
            if data['err']['code'] == '98':  # Login failed / Invalid auth token
                return authenticate()
            else:
                click.secho("Error: {}{}.".format(data['err']['code'], data['err']['msg']))
                sys.exit('Unexpected Error {} occurred.'.format(data['err']['code']))

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

    data = handle_response(requests.get(methods_url, params=params))

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

    r_auth = requests.get(auth_url, params=params)

    if r_auth.status_code != 200:
        click.secho("Error ({}:{}) connecting to Remember the Milk. Please "
                        "try again later.".format(r_auth.status_code, r_auth.reason), fg='red')
        sys.exit(1)

    click.echo('')
    click.echo('Please open the following link in your browser in order to '
               'approve authentication from Remember the Milk:')
    click.echo('')
    click.echo(r_auth.url)
    click.echo('')

    # pause the application while the user approves authentication
    value = click.prompt('Press any key and then press enter to continue.')

    # now get the authentication token
    params = {'api_key':API_KEY,
              'method':'rtm.auth.getToken',
              'format':'json',
              'frob':frob}

    # sign every request
    params['api_sig'] = make_api_sig(params)

    token_r = requests.get(methods_url, params=params)

    if token_r.status_code != 200:
        click.secho("Error ({}:{}) connecting to Remember the Milk. Please " \
                    "try again later.".format(token_r.status_code, token_r.reason), fg='red')
        sys.exit(1)
    else:
        data = token_r.json()['rsp']

    settings['token'] = data['auth']['token']
    settings['username'] = data['auth']['user']['username']
    settings['name'] = data['auth']['user']['fullname']

    save(settings)
    click.echo('')
    click.echo('Congrats, {}, your account is authenticated!'.format(settings['name']))

    return


def get_lists():
    """ Get all of the user's lists."""

    params = {'api_key':API_KEY,
              'method':'rtm.lists.getList',
              'format':'json',
              'auth_token':settings['token']}

    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    return data['lists']['list']


def get_tasks(list_name='', tag='', status=''):
    ''' Return list of Task objects by by various attributes.

    Inputs:
        -list_name: name of list_name
        -tag: name of tag
        -status: completed or incomplete
    '''

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

    data = handle_response(requests.get(methods_url, params=params))
    rtm_tasks = data['tasks']

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


def split_tasks(tasks):
    '''
    Take all tasks and return two lists - one of completed tasks and one
    of incomplete tasks, sorted by either completed date or due date.
    '''

    completed_tasks = []
    incomplete_tasks = []

    for task in tasks:
        if not task.completed:
            incomplete_tasks.append(task)
        else:
            completed_tasks.append(task)

    if completed_tasks:
        completed_tasks.sort(key=lambda t: t.completed)
    if incomplete_tasks:
        incomplete_tasks.sort(key=lambda t: t.due)

    return completed_tasks, incomplete_tasks


def display_tasks(list_name, tasks, status, command, filename=''):
    ''' Display tasks either in terminal or as pdf. '''

    completed_tasks = []
    incomplete_tasks = []

    tasks_as_lists = []
    completed_tasks_as_lists = []
    incomplete_tasks_as_lists = []

    # include list name in heading if getting tasks from particular list
    if list_name:
        heading1 = list_name + ' - '
    else:
        heading1 = ''

    # set up pdf
    if command == 'export':
        doc = SimpleDocTemplate(filename+'.pdf', pagesize=letter)
        styles=getSampleStyleSheet()
        table_style = TableStyle([('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                                  ('BOX', (0,0), (-1,-1), 1.25, colors.black),
                                 ])
        story = []



    if status and status == 'incomplete':
        heading1 += str(len(tasks)) + ' incomplete tasks'
        tasks.sort(key=lambda t: t.due)  # sort by due date
        incomplete_tasks_as_lists.append(['Task', 'Due'])

        for task in tasks:
            incomplete_tasks_as_lists.append(task.convert_to_list())

        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))
            t = Table(incomplete_tasks_as_lists)
            t.setStyle(table_style)
            story.append(t)
        elif command == 'tasks':
            print(tabulate(incomplete_tasks_as_lists, headers="firstrow", tablefmt="fancy_grid"))

    elif status and status == 'completed':
        heading1 += str(len(tasks)) + ' completed tasks'
        tasks.sort(key=lambda t: t.completed)  # sort by completed date
        completed_tasks_as_lists.append(['Task', 'Completed'])

        for task in tasks:
            completed_tasks_as_lists.append(task.convert_to_list())

        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))
            t = Table(completed_tasks_as_lists)
            t.setStyle(table_style)
            story.append(t)
        if command == 'tasks':
            print(tabulate(completed_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))

    else:
        # page header
        heading1 += str(len(tasks)) + ' tasks'

        # table headers
        completed_tasks_as_lists.append(['Task', 'Completed'])
        incomplete_tasks_as_lists.append(['Task', 'Due'])

        # create separate lists for completed and incomplete tasks
        completed_tasks, incomplete_tasks = split_tasks(tasks)
        completed_tasks.sort(key=lambda t: t.completed)  # sort by completed date
        incomplete_tasks.sort(key=lambda t: t.due)  # sort by due date

        # convert from Task objects to lists
        for task in completed_tasks:
            completed_tasks_as_lists.append(task.convert_to_list())
        for task in incomplete_tasks:
            incomplete_tasks_as_lists.append(task.convert_to_list())

        # export to pdf
        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))
            story.append(Paragraph(str(len(completed_tasks)) + ' completed tasks', styles['Heading2']))
            t = Table(completed_tasks_as_lists)
            t.setStyle(table_style)
            story.append(t)

            story.append(Paragraph(str(len(incomplete_tasks)) + ' incomplete tasks', styles['Heading2']))
            t = Table(incomplete_tasks_as_lists)
            t.setStyle(table_style)
            story.append(t)

        # display in terminal
        elif command == 'tasks':
            print(tabulate(incomplete_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))
            print(tabulate(completed_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))

    if command == 'export':
        doc.build(story)

    return


################################################################################
# commands
################################################################################
@click.group()
def main():
    """Don't Forget the Python: command-line interface for Remember the Milk.

    Type "<command> --help" to see options and additional info."""


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

    return display_tasks(list_name, tasks, status, 'tasks')


    # this was the verbose version
    # for task in tasks:
    #     print(task.name, end='')
    #     if task.due:
    #         print(' (due: ' + task.due +')')
    #     else:
    #         print('')
    #     if verbose:
    #         if task.tags:
    #             print(' tags: ', end='')
    #             for tag in task.tags:
    #                 print(tag, end=', ')
    #             print('')
    #         if task.notes:
    #             for note in task.notes:
    #                 print(' note: ' + note)
    #         if task.url:
    #             print(' url: ' + task.url)
    #         if task.priority:
    #             print(' priority: ' + task.priority)
    #         if task.participants:
    #             for participant in task.participants:
    #                 print(' participant: ' + participant)
    #         print('')


@main.command()
@click.option('--list_name', '-l', default='', help="List name.")
@click.option('--tag', '-t', default='', help="Tasks with a particular tag.")
@click.option('--incomplete', '-i', 'status', flag_value='incomplete', help="Incomplete tasks only.")
@click.option('--completed', '-c', 'status', flag_value='completed', help="Completed tasks only.")
@click.option('--filename', '-f', default='remember the milk tasks', help="Name of file to create.")
# @click.option('--days', '-d', default=0, help="For completed tasks, number of days since completed.")
def export(list_name, tag, status, filename):
    """Export tasks to pdf."""

    try:
        tasks = get_tasks(list_name, tag, status)
    except NoTasksException:
        click.secho("No tasks found with those parameters.", fg='red')
        return
    except NoListException:
        click.secho('No list by that name found.', fg='red')
        return

    return display_tasks(list_name, tasks, status, 'export', filename)


if __name__ == "__main__":
    main()
