#!python3


import random
import string

import pytest
import arrow

from dftp.app import Task, convert_to_list


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
    ''' Create on task with provided values. '''
    ts_data = dict(zip(taskseries_keys, ts_values))
    t_data = dict(zip(task_keys, t_values))
    return Task(ts_data, t_data)


@pytest.fixture(params=create_random_tasks(1))
def tasks_one_random(request):
    return request.param


@pytest.fixture(params=create_random_tasks(10))
def tasks_10_random(request):
    return request.param


#this should raise an exception
def test_task_id_0():
    ts_values = [0, 'do this', '', '', '', '']
    t_values = [arrow.utcnow().isoformat(), '', 1]
    a = create_one_task(ts_values, t_values)
    assert isinstance(a.id, int) is True


def test_id_is_int_one(tasks_one_random):
    assert isinstance(tasks_one_random.id, int) is True


def test_convert_one_random_task_to_list(tasks_one_random):
    a = convert_to_list(tasks_one_random.name, tasks_one_random.due, 'tasks')
    assert isinstance(a, list) is True


# This one is unncessary, just testing out different ways to run tests.
@pytest.mark.xfail()
def test_convert_one_random_task_to_list_fail(tasks_one_random):
    a = convert_to_list(tasks_one_random.name, tasks_one_random.due, 'tasks')
    assert isinstance(a, list) is False


def test_id_is_int_10_random(tasks_10_random):
    assert isinstance(tasks_10_random.id, int) is True


def test_convert_10_random_tasks_to_list(tasks_10_random):
    a = convert_to_list(tasks_10_random.name, tasks_10_random.due, 'tasks')
    assert isinstance(a, list) is True
