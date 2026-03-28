"""semantic-tx CLI 主入口。"""

import click

from semantic_transmission import __version__
from semantic_transmission.cli.check import check
from semantic_transmission.cli.demo import demo
from semantic_transmission.cli.download import download
from semantic_transmission.cli.receiver import receiver
from semantic_transmission.cli.sender import sender


@click.group()
@click.version_option(version=__version__, prog_name="semantic-tx")
def cli():
    """语义传输系统 CLI 工具。"""


cli.add_command(sender)
cli.add_command(receiver)
cli.add_command(demo)
cli.add_command(check)
cli.add_command(download)

if __name__ == "__main__":
    cli()
