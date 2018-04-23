import click
import requests

endpoint = 'https://api.rememberthemilk.com/services/rest/'

https://www.rememberthemilk.com/services/auth/

https://api.rememberthemilk.com/services/rest/?method=rtm.test.echo&api_key=123456789&name=value

@click.group()
@click.option('--verbose', is_flag=True)
def main(verbose):
    if verbose:
        click.echo("We are in verbose mode.")

@main.command()
@click.argument('out', type=click.File('w'), default='-')
@click.option('--format', type=str, help="File format.")
def say(out, format):
    """Command line interface for Remember the Milk."""
    click.echo('Hello World!')
    r = requests.get('https://api.github.com/user',

if __name__ == "__main__":
    main()
