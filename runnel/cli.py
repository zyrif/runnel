import json
from typing import Optional

import anyio
import typer

from runnel.utils import get_object
from runnel.worker import Worker
from runnel.exceptions import Misconfigured

cli = typer.Typer()
processor = typer.Typer()
cli.add_typer(processor, name="processor")


@cli.command()
def worker(
        app: str,
        processors: str = "all",
        django: bool = False,
        django_settings_module: Optional[str] = typer.Option(
            None,
            help="Python path to Django's settings.py file",
            show_default=False,
        ),
    ):
    """
    Run a worker for all processors of the given app, or just the processors given in a
    comma-separated string.

    Examples
    --------
    Assuming 'myapp/example.py' contains your Runnel app object and is on PYTHONPATH:

    .. code-block:: bash

        $ runnel worker myapp.example:myapp

    Or for specific processors:

    .. code-block:: bash

        $ runnel worker myapp.example:myapp --processors=myproc1,myproc2

    To initialize Django if you're working with a Django project:

    .. code-block:: bash
    
        $ runnel worker myapp.example:myapp --django

    To provide a custom path to the Django project's settings file:
    (Assuming myproject/settings.py is your django settings file)

    .. code-block:: bash

        $ runnel worker myapp.example:myapp --django --django-settings-module myproject.settings
    """
    if django:
        try:
            import os
            import django
            from django.core.checks import run_checks
            assert os.environ.get("DJANGO_SETTINGS_MODULE") or django_settings_module

            os.environ.setdefault("DJANGO_SETTINGS_MODULE", django_settings_module)
            django.setup()
            run_checks()

        except ImportError:
            raise Misconfigured("Django is not properly installed")

        except AssertionError:
            raise Misconfigured("'DJANGO_SETTINGS_MODULE' environment variable must be present if django-settings-module flag is not provided")


    obj = get_object(app)
    Worker(obj).start(processors.split(",") if processors != "all" else "all")


@cli.command()
def send(stream: str, value: str):
    """
    Send a given JSON-encoded value to a stream.

    Examples
    --------
    Assuming 'myapp/example.py' contains a stream called 'actions':

    .. code-block:: bash

        $ runnel send myapp.example:actions "{\\"user_id\\": 1, \\"type\\": \\"signup\\"}"
    """
    obj = get_object(stream)
    anyio.run(obj.send, obj.record(**json.loads(value)))


@cli.command()
def sendmany(stream: str, file: typer.FileText):
    """
    Send multiple JSON-encoded values to a stream in a pipelined transaction.

    Examples
    --------
    .. code-block:: bash

        $ echo "{\\"user_id\\": 1, \\"type\\": \\"signup\\"}" >> data.jsonl
        $ echo "{\\"user_id\\": 2, \\"type\\": \\"signup\\"}" >> data.jsonl

    Assuming 'myapp/example.py' contains a stream called 'actions':

    .. code-block:: bash

        $ runnel sendmany myapp.example:actions data.jsonl
    """
    obj = get_object(stream)
    anyio.run(obj.send, *[obj.record(**json.loads(value)) for value in file])


@processor.command()
def reset(name: str, start: str = "0"):
    """
    Reset the processor's starting ID and event backlog.

    Notes
    -----
    This will destroy and recreate the Redis consumer group(s) associated with the
    processor and should be run once all workers have been shut down.

    Examples
    --------
    Assuming 'myapp/example.py' contains a processor called 'printer':

    .. code-block:: bash

        runnel processor reset myapp.example:printer --start="0"
    """
    obj = get_object(name)
    anyio.run(obj.reset, start)
