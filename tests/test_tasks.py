#!python3

import random
import string

import pytest
import arrow

from dftp.app import Task, convert_to_list, create_Task_list, NoTasksException, \
    human_date_to_arrow, UnrecognizedDateFormat, MonthOrDayTooHigh, format_date_display


# dictionary keys for variables to create Tasks
taskseries_keys = ['id', 'name', 'url', 'tags', 'notes', 'participants']
task_keys = ['due', 'completed', 'priority']

# user timezone used in creating Task.is_overdue

config = {'USER SETTINGS': {'timezone':'America/New_York'}}

def create_random_tasks(number_of_tasks):
    ''' Creates list of *number_of_tasks* Task objects, populated with random values.'''

    list_of_taskseries_values = []
    list_of_task_values = []

    for i in range(number_of_tasks):
        taskseries_values = [i,
                  ''.join(random.choices(string.ascii_lowercase, k=10)),
                  ''.join(random.choices(string.ascii_lowercase, k=10)),
                  [''.join(random.choices(string.ascii_lowercase, k=10)),
                   ''.join(random.choices(string.ascii_lowercase, k=10))],
                  [''.join(random.choices(string.ascii_lowercase, k=10)),
                   ''.join(random.choices(string.ascii_lowercase, k=10))],
                  {'contact': [{'fullname':''.join(random.choices(string.ascii_lowercase, k=10))}]}
                 ]
        list_of_taskseries_values.append(taskseries_values)

        task_values = [arrow.utcnow().shift(hours=random.randint(-3, 7)).isoformat(),
                       arrow.utcnow().shift(hours=random.randint(1, 12)).isoformat(),
                       random.choice([1, 2, 3, 'N'])]
        list_of_task_values.append(task_values)

    tasks = []
    for i in range(number_of_tasks):
        task_series_data = dict(zip(taskseries_keys, list_of_taskseries_values[i]))
        task_data = dict(zip(task_keys, list_of_task_values[i]))
        tasks.append(Task(task_series_data, task_data))

    return tasks


def create_one_task(ts_values, t_values):
    ''' Create one task with provided values. '''
    ts_data = dict(zip(taskseries_keys, ts_values))
    t_data = dict(zip(task_keys, t_values))
    return Task(ts_data, t_data)


@pytest.fixture(params=create_random_tasks(1))
def tasks_one_random(request):
    return request.param


@pytest.fixture(params=create_random_tasks(10))
def tasks_10_random(request):
    return request.param


def test_convert_one_random_task_to_list(tasks_one_random):
    a = convert_to_list('print', tasks_one_random.name, tasks_one_random.due)
    assert isinstance(a, list) is True


def test_convert_10_random_tasks_to_list(tasks_10_random):
    a = convert_to_list('print', tasks_10_random.name, tasks_10_random.due)
    assert isinstance(a, list) is True


################################################################################
# some common dates to use in various date testing
################################################################################

# no need to use timezones in date creation, since this is run locally

# arrow objects in isoformat
today = arrow.now()
tomorrow = arrow.now().shift(days=1)
yesterday = arrow.now().shift(days=-1)

# before and after midnight to ensure timezones conversion working correctly
today_11pm = arrow.now().replace(hour=23, minute=0)
today_1am = arrow.now().replace(hour=1, minute=0)
yesterday_11pm = arrow.now().shift(days=-1).replace(hour=23, minute=0)
yesterday_1am = arrow.now().shift(days=-1).replace(hour=1, minute=0)
tomorrow_11pm = arrow.now().shift(days=+1).replace(hour=23, minute=0)
tomorrow_1am = arrow.now().shift(days=+1).replace(hour=1, minute=0)

# str format for initial task creation
today_str = str(today)
tomorrow_str = str(tomorrow)
yesterday_str = str(yesterday)
today_11pm_str = str(today_11pm)
today_1am_str = str(today_1am)
yesterday_11pm_str = str(yesterday_11pm)
yesterday_1am_str = str(yesterday_1am)
tomorrow_11pm_str = str(tomorrow_11pm)
tomorrow_1am_str = str(tomorrow_1am)

# arrow datetime format for processing dates in various functions
today_dt = today.datetime
tomorrow_dt = tomorrow.datetime
yesterday_dt = yesterday.datetime
today_11pm_dt = today_11pm.datetime
today_1am_dt = today_1am.datetime
yesterday_11pm_dt = yesterday_11pm.datetime
yesterday_1am_dt = yesterday_1am.datetime
tomorrow_11pm_dt = tomorrow_11pm.datetime
tomorrow_1am_dt = tomorrow_1am.datetime


def initialize_dates(due='', due_before='', due_after='',
                     completed_on='', completed_before ='',
                     completed_after = ''):
    ''' set up dates dictionary, since tasks() will set each to '' if not
    passed by user '''
    return {'due':due, 'due_before':due_before, 'due_after':due_after,
            'completed_on':completed_on, 'completed_before':completed_before,
            'completed_after':completed_after}

################################################################################
# human_date_to_arrow should take date in a limited number of formats and
# return an Arrow datetime.date object
# 'due' or 'completed' are used to assume date based on current year if user
# did not supply yy or yyyy in input
################################################################################

# first test the custom options (today, yesterday, tomorrow)
def test_user_date_today():
    assert human_date_to_arrow('today', 'due') == today.date()


def test_user_date_yesterday():
    assert human_date_to_arrow('yesterday', 'due') == yesterday.date()


def test_user_date_tomorrow():
    assert human_date_to_arrow('tomorrow', 'due') == tomorrow.date()


# now test the standard date formats

def test_user_date_today_m_d_yy_1():
    user_today = arrow.now().format('M/D/YY')
    assert human_date_to_arrow(user_today, 'due') == today.date()


def test_user_date_today_m_d_yy_2():
    user_yesterday = arrow.now().shift(days=-1).format('M/D/YY')
    assert human_date_to_arrow(user_yesterday, 'due') == yesterday.date()


def test_user_date_today_m_d_yy_3():
    user_tomorrow = arrow.now().shift(days=1).format('M/D/YY')
    assert human_date_to_arrow(user_tomorrow, 'due') == tomorrow.date()


@pytest.mark.parametrize('date',
                         ['8/5/18', '08/5/18', '8/05/18', '08/05/18',
                          '8/5/2018', '08/5/2018', '8/05/2018', '08/05/2018',
                          '8-5-18', '08-05-2018',
                          '8.5.18', '08.05.2018',
                          '08.05-2018'])
def test_user_date_1(date):
    assert human_date_to_arrow(date, 'due') == arrow.get('2018-08-05').date()


@pytest.mark.parametrize('date',
                         ['1/1/17', '01/1/17', '1/01/17', '01/01/17',
                          '1/1/2017', '01/1/2017', '1/01/2017', '01/01/2017',
                          '1-1-17', '01-01-2017',
                          '1.1.17', '01.01.2017',
                          '01.01-2017'])
def test_user_date_2(date):
    assert human_date_to_arrow(date, 'due') == arrow.get('2017-01-01').date()


@pytest.mark.parametrize('date',
                         ['12/31/19', '12/31/2019', '12-31-19', '12.31.19',
                          '12.31-2019'])
def test_user_date_3(date):
    assert human_date_to_arrow(date, 'due') == arrow.get('2019-12-31').date()


# test dates given by user with no year

def test_human_date_to_arrow_date_m_d_due_1():
    # if no year supplied by user, for one of the due filters, will be assumed
    # to be next year if that date has passed in current year
    yesterday_m_d = str(arrow.now().shift(days=-1).format('M/D'))
    yesterday_next_year = arrow.now().shift(days=-1, years=1).date()
    assert human_date_to_arrow(yesterday_m_d, 'due') == yesterday_next_year


def test_human_date_to_arrow_date_m_d_due_2():
    # if no year supplied by user, for one of the due filters, will be assumed
    # to be this year if that date has not passed in current year
    tomorrow_m_d = str(arrow.now().shift(days=1).format('M/D'))
    assert human_date_to_arrow(tomorrow_m_d, 'due') == tomorrow.date()


def test_human_date_to_arrow_date_m_d_complete_1():
    # if no year supplied by user, for one of the complete filters, will be assumed
    # to be this year if that date has passed in current year
    yesterday_m_d = str(arrow.now().shift(days=-1).format('M/D'))
    assert human_date_to_arrow(yesterday_m_d, 'completed') == yesterday.date()


def test_human_date_to_arrow_date_m_d_complete_2():
    # if no year supplied by user, for one of the complete filters, will be assumed
    # to be last year if that date has not passed in current year
    tomorrow_m_d = str(arrow.now().shift(days=1).format('M/D'))
    tomorrow_last_year = arrow.now().shift(days=1, years=-1).date()
    assert human_date_to_arrow(tomorrow_m_d, 'completed') == tomorrow_last_year


# test exceptions

@pytest.mark.parametrize('date',
                          ['0/5/18', '8/0/18', '123/5/18', '8/123/18',
                           '8/5/201', '8/5/20181',
                           'a/5/18', '8/ab/2018', '8/5/ab',
                           '8 5 18'])
def test_incorrect_user_date_raises_UnrecognizedDateFormat(date):
    with pytest.raises(UnrecognizedDateFormat):
        human_date_to_arrow(date, 'due')


@pytest.mark.parametrize('date',
                          ['0/5', '8/0', '123/5', '8/123',
                           'a/5', '8/ab',
                           '8 5',
                           '8/5/', '8-5-', '/8/5'])
def test_incorrect_user_date_no_year_raises_UnrecognizedDateFormat(date):
    with pytest.raises(UnrecognizedDateFormat):
        human_date_to_arrow(date, 'due')


@pytest.mark.parametrize('date',
                          ['13/5/18', '8/32/18', '13/5', '8/32'])
def test_incorrect_user_date_raises_MonthOrDayTooHigh(date):
    with pytest.raises(MonthOrDayTooHigh):
        human_date_to_arrow(date, 'due')


################################################################################
# test format_date_display() - date shown to user after task list returned
################################################################################

# format date display converts iso string to month abbreviation, day, year
# (and possibly time)

def test_format_date_never():
    ''' date of "never" should stay "never" '''
    assert format_date_display('never') == 'never'

def test_format_date_display_no_due_or_completed_time():
    ''' date with time at midnight should not display time.'''
    today_midnight = arrow.now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert format_date_display(today_midnight.isoformat()) == today_midnight.format('MMM D, YYYY')

def test_format_date_display_due_or_completed_time():
    ''' date with time at midnight should not display time.'''
    # aug_5_18_8am = arrow.get(datetime(2013, 5, 5), 'US/Pacific')
    aug_5_18_8am = arrow.now().replace(year=2018, month=8, day=5, hour=8, minute=0,
                                       second=0, microsecond=0)
    assert format_date_display(aug_5_18_8am.isoformat()) == 'Aug 5, 2018 8:00 am'


################################################################################
# functions for mocking RTM list/task structure and response.
################################################################################

def mock_rtm_taskseries(id, name, url='', tags=[], notes=[], participants=[],
    due='', completed='', priority=''):
    '''
    This creates a taskseries (which contains most task attributes, including
    a *task* attribute/element that contains other attributes) to mirror the
    structure from RTM, where taskseries are within a list of lists.

    *due* and *completed* are dates in strings in iso format
    '''

    taskseries = {}
    taskseries['id'] = id
    taskseries['name'] = name
    taskseries['url'] = url
    taskseries['tags'] = tags
    taskseries['notes'] = notes
    taskseries['participants'] = participants

    task = {}
    task['due'] = due
    task['completed'] = completed
    task['priority'] = priority
    taskseries['task'] = [task]

    return taskseries


def make_list_of_rtm_lists(tasks):
    '''
    Create a list of lists, matching format returned from RTM, where each list
    (within the larger list) is an RTM list of taskseries.
    All taskseries here are within a mock RTM list.
    '''

    rtm_list = {}
    rtm_list['id'] = 1
    rtm_list['taskseries'] = []

    for task in tasks:
        rtm_list['taskseries'].append(task)

    list_of_rtm_lists = [rtm_list]

    return list_of_rtm_lists


################################################################################
# testing create_Task_list, using functions mocking RTM task/list structure and
# response, with no date filters
################################################################################

def test_create_Task_list_returns_1_task():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this'))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    assert len(task_list) == 1


def test_create_Task_list_returns_2_tasks():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this'))
    tasks.append(mock_rtm_taskseries(2, 'do that'))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    assert len(task_list) == 2


def test_create_Task_list_returns_10_tasks():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'one'))
    tasks.append(mock_rtm_taskseries(2, 'two'))
    tasks.append(mock_rtm_taskseries(3, 'three'))
    tasks.append(mock_rtm_taskseries(4, 'four'))
    tasks.append(mock_rtm_taskseries(5, 'five'))
    tasks.append(mock_rtm_taskseries(6, 'six'))
    tasks.append(mock_rtm_taskseries(7, 'seven'))
    tasks.append(mock_rtm_taskseries(8, 'eight'))
    tasks.append(mock_rtm_taskseries(9, 'nine'))
    tasks.append(mock_rtm_taskseries(10, 'ten'))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    assert len(task_list) == 10


def test_create_Task_list_returns_one_task_with_correct_due_date():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this', due=today))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    assert task_list[0].due == today


def test_create_Task_list_returns_one_task_with_correct_completed_date():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this', completed=today))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    assert task_list[0].completed == today


def test_create_Task_list_returns_one_task_with_correct_due_and_completed_date():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this', due=yesterday, completed=today))

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=initialize_dates())

    failure = 0
    if task_list[0].completed != today or task_list[0].due != yesterday:
        failure = 1

    assert failure == 0


def test_create_Task_list_empty_task_list_raises_NoTasksException():
    with pytest.raises(NoTasksException):
        create_Task_list([])


################################################################################
# testing create_Task_list, with various date filters
################################################################################

def test_create_Task_list_returns_one_task_with_due_date():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this', due=today_str))
    tasks.append(mock_rtm_taskseries(2, 'do that', due=yesterday_str))
    tasks.append(mock_rtm_taskseries(3, 'do nothing', due=tomorrow_str))

    dates = initialize_dates(due='today')

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

    assert len(task_list) == 1


def test_create_Task_list_returns_5_tasks_with_due_after():
        tasks = []
        due_date_1_str = str(arrow.get('2018-08-05'))
        due_date_2_str = str(arrow.get('2018-08-07'))
        tasks.append(mock_rtm_taskseries(1, 'do this', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', due=due_date_2_str))

        dates = initialize_dates(due_after='8/5/18')

        task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

        assert len(task_list) == 5

def test_create_Task_list_returns_2_tasks_with_due_before():
        tasks = []
        due_date_1_str = str(arrow.get('2018-08-05'))
        due_date_2_str = str(arrow.get('2018-08-07'))
        tasks.append(mock_rtm_taskseries(1, 'do this', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', due=due_date_2_str))

        dates = initialize_dates(due_before='8/7/18')

        task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

        assert len(task_list) == 2


def test_create_Task_list_returns_one_task_with_completed_date():
    tasks = []
    tasks.append(mock_rtm_taskseries(1, 'do this', completed=today_str))
    tasks.append(mock_rtm_taskseries(2, 'do that', completed=yesterday_str))
    tasks.append(mock_rtm_taskseries(3, 'do nothing', completed=yesterday_str))

    dates = initialize_dates(completed_on='today')

    task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

    assert len(task_list) == 1


def test_create_Task_list_returns_5_tasks_with_completed_after():
        tasks = []
        past_date_1_str = str(arrow.get('2018-08-05'))
        past_date_2_str = str(arrow.get('2018-08-06'))
        tasks.append(mock_rtm_taskseries(1, 'do this', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', completed=past_date_2_str))

        dates = initialize_dates(completed_after='8/5/18')

        task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

        assert len(task_list) == 5


def test_create_Task_list_returns_2_tasks_with_completed_before():
        tasks = []
        past_date_1_str = str(arrow.get('2018-08-05'))
        past_date_2_str = str(arrow.get('2018-08-06'))
        tasks.append(mock_rtm_taskseries(1, 'do this', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', completed=past_date_2_str))

        dates = initialize_dates(completed_before='8/6/18')

        task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

        assert len(task_list) == 2


def test_create_Task_list_between_dates():
        tasks = []
        due_date_1_str = str(arrow.get('2018-08-05'))
        due_date_2_str = str(arrow.get('2018-08-07'))
        due_date_3_str = str(arrow.get('2018-08-08'))
        due_date_4_str = str(arrow.get('2018-08-09'))
        tasks.append(mock_rtm_taskseries(1, 'do this', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', due=due_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', due=due_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', due=due_date_3_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', due=due_date_4_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', due=due_date_4_str))

        dates = initialize_dates(due_after='8/6/18', due_before='8/9/18')

        task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)

        assert len(task_list) == 3


# test exceptions

def test_create_Task_list_no_tasks_meeting_filters_raises_NoTasksException():
        tasks = []
        past_date_1_str = str(arrow.get('2018-08-05'))
        past_date_2_str = str(arrow.get('2018-08-06'))
        tasks.append(mock_rtm_taskseries(1, 'do this', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(2, 'do that', completed=past_date_1_str))
        tasks.append(mock_rtm_taskseries(3, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(4, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(5, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(6, 'do nothing', completed=past_date_2_str))
        tasks.append(mock_rtm_taskseries(7, 'do nothing', completed=past_date_2_str))

        dates = initialize_dates(completed_before='8/5/18')
        with pytest.raises(NoTasksException):
            task_list = create_Task_list(make_list_of_rtm_lists(tasks), dates=dates)
