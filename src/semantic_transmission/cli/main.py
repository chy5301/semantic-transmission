"""semantic-tx CLI 主入口。"""

import click

from semantic_transmission import __version__


@click.group()
@click.version_option(version=__version__, prog_name="semantic-tx")
def cli():
    """语义传输系统 CLI 工具。"""


if __name__ == "__main__":
    cli()
