#!python3

import sys
from pathlib import Path
import datetime
import textwrap
import hashlib
import configparser

import click
import requests
import arrow
from tabulate import tabulate

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


# If you want to develop your own application based off this one, please
# apply for a new API Key at https://www.rememberthemilk.com/services/api/keys.rtm
api_key = '4e1d92b0c92e573ca0aafcdee63705c2'
shared_secret = '648e3b6f390699b7'

auth_url = 'https://www.rememberthemilk.com/services/auth/'
methods_url = 'https://api.rememberthemilk.com/services/rest/'


# create or read config file (in user's home directory)
global config
config = configparser.ConfigParser()

global config_file
config_file = Path().home().joinpath('.dftp')

if config_file.is_file():
    config.read(config_file)
else:
    config['USER SETTINGS'] = {'token': '',
                               'username': '',
                               'name': '',
                               'timezone': '',
                               'dateformat': '',
                               'timeformat': ''}
    with open(config_file, 'w') as fp:
        config.write(fp)


################################################################################
# CLASSES
################################################################################
class Task:

    def __init__(self, taskseries, task):
        self.id = taskseries['id']
        self.name = taskseries['name']
        self.url = '' if not taskseries['url'] else taskseries['url']

        self.completed = task['completed']  # iso format, utc

        # keep due and completed times as strings in order to enable easy sorting later
        self.due = 'never' if not task['due'] else task['due']  # iso format, utc

        # also set up an arrow object (date only) to help deal with issue
        # of RTM setting tasks with no due time as midnight
        self.due_date = ''

        self.is_overdue = False

        # set due_date and is_overdue if the task has a due date(time)
        if self.due != 'never':
            task_due = arrow.get(task['due']).to(config['USER SETTINGS']['timezone'])

            self.due_date = task_due.date()

            # if it's due at midnight, it's due sometime that day, so don't
            # make it overdue unless date (not time) is past
            if str(task_due.time()) == '00:00:00':
                if task_due.date() < arrow.get().to(config['USER SETTINGS']['timezone']).date():
                    self.is_overdue = True
            else:
                if task_due < arrow.get(tzinfo=config['USER SETTINGS']['timezone']):
                    self.is_overdue = True

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


class BadDataException(Exception):
    pass

class NoTasksException(Exception):
    pass

class NoListException(Exception):
    pass


################################################################################
# API AUTHORIZATION FUNCTIONS
################################################################################
def handle_response(r):
    ''' Deal with common responses from RTM API.'''

    if r.status_code != 200:
        click.secho(textwrap.fill('Error ({}:{}) connecting to Remember the '
                'Milk. Please try again later.'.format(r.status_code, r.reason)), fg='red')
        sys.exit('Bad Status Code')
    else:
        data = r.json()['rsp']

        if data['stat'] != 'ok':
            if data['err']['code'] == '98':  # Login failed / Invalid auth token
                click.secho('Error with Remember the Milk Authentication.', fg='red')
                authenticate()
                return
            else:
                click.secho('Error: {}'.format(data['err']['msg']), fg='red')
                sys.exit('Error {}.'.format(data['err']['code']))

        return data


def make_api_sig(params):
    '''
    Creates an API signature as required by RTM. See
    https://www.rememberthemilk.com/services/api/authentication.rtm

    This creates a string consisting of the shared_secret provided by RTM concatenated
    with the sorted key/value pairs of the parameters to be sent. This api_sig
    then becomes another parameter sent with the request to RTM.
    '''

    api_sig = shared_secret + ''.join('{}{}'.format(key, value) for key, value in sorted(params.items()))
    api_sig = hashlib.md5(api_sig.encode('utf-8'))
    return api_sig.hexdigest()


def get_frob():
    ''' Returns *frob*. Part of the authentication process.'''

    params = {'method':'rtm.auth.getFrob',
              'api_key':api_key,
              'format':'json'}

    # create signature from existing params and add as parameter
    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    return data['frob']


def authenticate():
    '''
    Authenticates user to RTM and stores token and other settings to *config* file.

    See https://www.rememberthemilk.com/services/api/authentication.rtm
    '''

    frob = get_frob()
    params = {'api_key':api_key,
              'frob':frob,
              'perms':'read'}
    params['api_sig'] = make_api_sig(params)

    r_auth = requests.get(auth_url, params=params)

    if r_auth.status_code != 200:
        click.secho(textwrap.fill('Error ({}:{}) connecting to Remember the Milk. '
                'Please try again later.'.format(r_auth.status_code, r_auth.reason), fg='red'))
        sys.exit(1)

    click.echo('')
    click.echo(textwrap.fill('Please open the following link in your browser '
            'in order to approve authentication from Remember the Milk:'))
    click.echo('')
    click.echo(r_auth.url)
    click.echo('')

    click.pause(info='Press any key to continue.')

    # now get the authentication token
    params = {'api_key':api_key,
              'method':'rtm.auth.getToken',
              'format':'json',
              'frob':frob}

    # sign every request
    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    config['USER SETTINGS']['token'] = data['auth']['token']
    config['USER SETTINGS']['username'] = data['auth']['user']['username']
    config['USER SETTINGS']['name'] = data['auth']['user']['fullname']

    # get additional RTM settings from different method call
    params = {'api_key':api_key,
              'method':'rtm.settings.getList',
              'format':'json',
              'auth_token':config['USER SETTINGS']['token']}

    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    config['USER SETTINGS']['timezone'] = data['settings']['timezone']
    config['USER SETTINGS']['dateformat'] = data['settings']['dateformat']
    config['USER SETTINGS']['timeformat'] = data['settings']['timeformat']

    save(config)

    click.echo('')
    click.echo('Congrats, {}, your account is authenticated!'.format(config['USER SETTINGS']['name']))
    click.echo('')

    return


################################################################################
#  HELPER FUNCTIONS
################################################################################
def save(config):
    ''' Save user's RTM settings in config.ini.'''

    for key, value in config['USER SETTINGS'].items():
        config.set('USER SETTINGS', key, value)

    with open(config_file, 'w') as fp:
        config.write(fp)

    return


def get_lists():
    ''' Get all of the user's lists.'''

    params = {'api_key':api_key,
              'method':'rtm.lists.getList',
              'format':'json',
              'auth_token':config['USER SETTINGS']['token']}

    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    return data['lists']['list']


def get_tasks(list_name, tag, due, due_before, due_after, completed_on,
              completed_before, completed_after, status=''):
    ''' Return list of Task objects by various attributes.'''

    params = {'api_key':api_key,
              'method':'rtm.tasks.getList',
              'format':'json',
              'auth_token':config['USER SETTINGS']['token']}

    if list_name:
        rtm_lists = get_lists()

        list_id = ''
        for rtm_list in rtm_lists:
            if list_name == rtm_list['name']:
                list_id = rtm_list['id']

        if not list_id:
            raise NoListException

        params['list_id'] = list_id

    # completed_on, completed_before, and completed_after only apply to completed
    # dates, but the user may not include that flag, so set it
    if completed_on or completed_before or completed_after:
        status = 'completed'

    if status == 'completed':
        params['filter'] = 'status:completed'

    if status == 'incomplete':
        params['filter'] = 'status:incompleted'

    # if other options included, have to filter for thoese later since
    # the query can take only one params['filter'] parameter and it doesn't
    # seem like they can be chained together

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

    # further filter tasks by dates
    if due:
        tasks = [task for task in tasks if task.due_date and task.due_date == human_date_to_arrow(due, 'due')]
    if due_before:
        tasks = [task for task in tasks if task.due_date and task.due_date < human_date_to_arrow(due_before, 'due')]
    if due_after:
        tasks = [task for task in tasks if task.due_date and task.due_date > human_date_to_arrow(due_after, 'due')]
    if completed_on:
        tasks = [task for task in tasks if task.due_date and task.due_date == human_date_to_arrow(completed_on, 'completed')]
    if completed_before:
        tasks = [task for task in tasks if task.due_date and task.due_date < human_date_to_arrow(completed_before, 'completed')]
    if completed_after:
        tasks = [task for task in tasks if task.due_date and task.due_date > human_date_to_arrow(completed_after, 'completed')]

    if not tasks:
        raise NoTasksException

    # return status here in the case that the user chose options for a completed
    # date, and didn't also set the completed option
    return status, tasks


def split_list(all_tasks):
    '''
    Split list of all tasks into two lists - one of completed tasks and one
    of incomplete tasks, sorted by either completed date or due date.
    '''

    completed_tasks = []
    incomplete_tasks = []

    for task in all_tasks:
        if not task.completed:
            incomplete_tasks.append(task)
        else:
            completed_tasks.append(task)

    if completed_tasks:
        completed_tasks.sort(key=lambda t: t.completed)
    if incomplete_tasks:
        incomplete_tasks.sort(key=lambda t: t.due)

    return completed_tasks, incomplete_tasks

def human_date_to_arrow(date, type_of_filter):
    converted_date = ''

    # because we have to try each of these, the higher up in the list the given
    # format is, the quicker the result will be returned, so limit the number
    # of formats. (And be sure to inform user of preferred format in help text.)
    date_formats = ['M/D/YY', 'M/D', 'M/D/YYYY',
                    'MM/DD/YY', 'MM/D/YY',
                    'M/DD/YYYY',
                    'MM/DD/YYYY', 'MM/D/YYYY',
                    'M/DD/YY',
                    'MM/DD', 'MM/D',
                    'M/DD',
                    ]

    # those correspond to:
    # 8/5/18, 8/5, 8/5/2018
    # 08/05/18, 08/5/18
    # 8/05/2018
    # 08/05/2018, 08/5/2018
    # 8/05/18,
    # 08/05, 08/5
    # 8/05

    # set some custom dates
    if date.lower() == 'today':
        return arrow.now().date()
    elif date.lower() == 'tomorrow':
        return arrow.now().shift(days=+1).date()
    elif date.lower() == 'yesterday':
        return arrow.now().shift(days=-1).date()

    try:
        converted_date = arrow.get(date, date_formats).date()
        # if user didn't include year, arrow will set it to 1
        # assume they meant the next date in the future
        if converted_date.year == 1:
            date_current_year = date + ' ' + str(arrow.get().to(config['USER SETTINGS']['timezone']).year)

            # if date given is a due date, if not yet passed, use
            # current year, otherwise use next year.
            if type_of_filter == 'due':
                if arrow.get(date_current_year, date_formats).date() >= arrow.now().date():
                    converted_date = arrow.get(date_current_year, date_formats).date()
                else:
                    date =  date + ' ' + str(arrow.get().year + 1)
                    converted_date = arrow.get(date, date_formats).date()

            # if date given is a completed date, if it not yet in past, use
            # previous year, otherwise use current year
            if type_of_filter == 'completed':
                if arrow.get(date_current_year, date_formats).date() >= arrow.now().date():
                    date =  date + ' ' + str(arrow.get().year - 1)
                    converted_date = arrow.get(date, date_formats).date()
                else:
                    converted_date = arrow.get(date_current_year, date_formats).date()

        return converted_date

    except arrow.parser.ParserError:
        click.secho('Unrecognized date format', fg='red')
        return sys.exit()


def format_date(task_date):
    ''' Convert date to formatted string for displaying to user.'''

    # convert to arrow object and user's timezone
    if task_date != 'never':
        task_date = arrow.get(task_date).to(config['USER SETTINGS']['timezone'])

        # RTM stores tasks with no due time as midnight, so if that is the case,
        # only display date, otherwise full date/time
        if str(task_date.time()) == '00:00:00':
            return task_date.format('MMM D, YYYY')
        else:
            return task_date.format('MMM D, YYYY h:mm a')
    else:
        return task_date


def convert_to_list(task_name, task_date, command):
    ''' Returns Task as list, with task name text wrapped.'''
    if command == 'tasks':
        return ['\n'.join(textwrap.wrap(task_name, 50)), task_date]
    if command == 'export':
        return ['\n'.join(textwrap.wrap(task_name, 70)), task_date]


def display_tasks(list_name, tag, tasks, status, command, filename=''):
    ''' Display tasks either in terminal or as pdf. '''

    completed_tasks_as_lists = [['Task', 'Completed']]
    incomplete_tasks_as_lists = [['Task', 'Due']]

    if list_name:
        heading1 = list_name + ' - '
    elif tag:
        heading1 = tag + ' - '
    else:
        heading1 = ''

    if command == 'export':
        doc = SimpleDocTemplate(filename+'.pdf', pagesize=letter)
        styles=getSampleStyleSheet()
        table_style = TableStyle([('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                                  ('BOX', (0,0), (-1,-1), 1.25, colors.black),
                                 ])
        col1_width, col2_width = 340, 115
        red_text = ParagraphStyle('red', textColor = colors.red)
        story = []

    if status and status == 'incomplete':
        heading1 += str(len(tasks)) + ' incomplete tasks'
        tasks.sort(key=lambda t: t.due)

        for task in tasks:
            formatted_date = format_date(task.due)

            if task.is_overdue:
                if command == 'tasks':
                    formatted_date = click.style(formatted_date, fg='red')
                if command == 'export':
                    formatted_date = Paragraph(formatted_date, red_text)

            incomplete_tasks_as_lists.append(convert_to_list(task.name, formatted_date, command))

        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))
            t = Table(incomplete_tasks_as_lists, colWidths=(col1_width, col2_width))
            t.setStyle(table_style)
            story.append(t)
        elif command == 'tasks':
            click.secho('\nIncomplete Tasks', fg='green')
            print(tabulate(incomplete_tasks_as_lists, headers="firstrow", tablefmt="fancy_grid"))

    elif status and status == 'completed':
        heading1 += str(len(tasks)) + ' completed tasks'
        tasks.sort(key=lambda t: t.completed)

        for task in tasks:
            task.completed = format_date(task.completed)
            completed_tasks_as_lists.append(convert_to_list(task.name, task.completed, command))

        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))
            t = Table(completed_tasks_as_lists, colWidths=(col1_width, col2_width))
            t.setStyle(table_style)
            story.append(t)
        elif command == 'tasks':
            click.secho('\nCompleted Tasks', fg='green')
            print(tabulate(completed_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))

    else:
        heading1 += str(len(tasks)) + ' tasks'

        completed_tasks, incomplete_tasks = split_list(tasks)
        completed_tasks.sort(key=lambda t: t.completed)
        incomplete_tasks.sort(key=lambda t: t.due)

        for task in completed_tasks:
            task.completed = format_date(task.completed)
            completed_tasks_as_lists.append(convert_to_list(task.name, task.completed, command))

        for task in incomplete_tasks:
            formatted_date = format_date(task.due)
            if task.is_overdue:
                if command == 'tasks':
                    formatted_date = click.style(formatted_date, fg='red')
                if command == 'export':
                    formatted_date = Paragraph(formatted_date, red_text)
            incomplete_tasks_as_lists.append(convert_to_list(task.name, formatted_date, command))

        if command == 'export':
            story.append(Paragraph(heading1, styles['Heading1']))

            story.append(Paragraph(str(len(incomplete_tasks)) + ' incomplete tasks', styles['Heading2']))
            t = Table(incomplete_tasks_as_lists, colWidths=(col1_width, col2_width))
            t.setStyle(table_style)
            story.append(t)

            story.append(Paragraph(str(len(completed_tasks)) + ' completed tasks', styles['Heading2']))
            t = Table(completed_tasks_as_lists, colWidths=(col1_width, col2_width))
            t.setStyle(table_style)
            story.append(t)

        elif command == 'tasks':
            click.secho('\nIncomplete Tasks', fg='green')
            print(tabulate(incomplete_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))
            click.secho('\nCompleted Tasks', fg='green')
            print(tabulate(completed_tasks_as_lists, headers="firstrow", tablefmt='fancy_grid'))

    if command == 'export':
        doc.build(story)

    return


################################################################################
# commands
################################################################################
@click.group()
def main():
    '''Don't Forget the Python: command-line interface for Remember the Milk.

    Type "<command> --help" to see options and additional info.'''

    # authenticate user if not yet authenticated or ini file corrupted
    if not config['USER SETTINGS']['token']:
        authenticate()

    # # reauthenticate user if token expired or if they revoked authorization
    params = {'api_key':api_key,
              'method':'rtm.auth.checkToken',
              'format':'json',
              'auth_token':config['USER SETTINGS']['token']}

    params['api_sig'] = make_api_sig(params)

    data = handle_response(requests.get(methods_url, params=params))

    return


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
@click.option('--due', '-d', default='', help='Tasks due on particular date.')
@click.option('--due_before', '-db', default='', help='Tasks due before a particular date.')
@click.option('--due_after', '-da', default='', help='Tasks due after a particular date.')
@click.option('--completed_on', '-co', default='', help='Tasks completed on a particular date.')
@click.option('--completed_before', '-cb', default='', help='Tasks completed before a particular date.')
@click.option('--completed_after', '-ca', default='', help='Tasks completed after a particular date.')
def tasks(list_name, tag, status, due, due_before, due_after, completed_on,
        completed_before, completed_after):
    '''
    List your tasks. All options can be used together, except, of course,
    for -i and -c.

    Although dates can be given in a variety of formats, unless you choose
    "today", "yesterday", or "tomorrow" (without the quotes), the result will be
    returned quickest if you use the format M/D/YY, e.g. 8/5/18. Months should always
    precede days.

    Use the before and after date options together in order to get tasks between two dates.
    '''

    try:
        status, tasks = get_tasks(list_name, tag, due, due_before, due_after,
            completed_on, completed_before, completed_after, status=status)
    except NoTasksException:
        click.secho('No tasks found with those parameters.', fg='red')
        return
    except NoListException:
        click.secho('No list by that name found.', fg='red')
        return

    return display_tasks(list_name, tag, tasks, status, 'tasks')


@main.command()
@click.option('--list_name', '-l', default='', help="Tasks from a particular list.")
@click.option('--tag', '-t', default='', help="Tasks with a particular tag.")
@click.option('--incomplete', '-i', 'status', flag_value='incomplete', help="Incomplete tasks only.")
@click.option('--completed', '-c', 'status', flag_value='completed', help="Completed tasks only.")
@click.option('--filename', '-f', default='RTM tasks', help="Name of file to create.")
@click.option('--due', '-d', 'due', default='', help='Tasks due on particular date.')
@click.option('--due_before', '-db', default='', help='Tasks due before a particular date.')
@click.option('--due_after', '-da', default='', help='Tasks due after a particular date.')
@click.option('--completed_on', '-co', default='', help='Tasks completed on particular date.')
@click.option('--completed_before', '-cb', default='', help='Tasks completed before a particular date.')
@click.option('--completed_after', '-ca', default='', help='Tasks completed after a particular date.')
def export(list_name, tag, status, filename, due, due_before, due_after, completed_on,
           completed_before, completed_after):
    '''
    Export your tasks to pdf. All options can be used together, except, of
    course, for -i and -c.

    Although dates can be given in a variety of formats, unless you choose
    "today", "yesterday", or "tomorrow" (without the quotes), the result will be
    returned quickest if you use the format M/D/YY, e.g. 8/5/18. Months should always
    precede days.

    Use the before and after date options together in order to get tasks between two dates.
    '''

    try:
        status, tasks = get_tasks(list_name, tag, due, due_before, due_after, completed_on,
            completed_before, completed_after, status=status)
    except NoTasksException:
        click.secho('No tasks found with those parameters.', fg='red')
        return
    except NoListException:
        click.secho('No list by that name found.', fg='red')
        return

    return display_tasks(list_name, tag, tasks, status, 'export', filename)


if __name__ == "__main__":
    main()
