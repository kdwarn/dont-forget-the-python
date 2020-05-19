# Don't Forget the Python

Don't Forget the Python is a command-line interface for [Remember the Milk](https://www.rememberthemilk.com), an online task-management system.

Remember the Milk is very good at what it does - and is very easy to use in the browser and various apps - so Don't Forget the Python does not focus on duplicating its abilities, but instead adds a couple features that RTM doesn't currently provide, like exporting your tasks to pdf and printing your lists and tasks to the terminal. Currently, only a simplified version of tasks is supported (name and due or completed date).

## Installation

Use [pipx](https://pypi.org/project/pipx/): `pipx install dftp`

## Usage

From a terminal, run `dftp` and the list of available commands will be shown, including full help documentation.

## New in Version 0.2.0

You can now filter tasks by various due and/or completed dates - on, before, or after a date (and between two dates). Run `dftp tasks --help` in a terminal to see the options.

## Disclaimer

This CLI uses the Remember The Milk API but is not endorsed or certified by Remember The Milk.
