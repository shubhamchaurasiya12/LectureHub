# run.py
import click
from app import create_app
from app.utils import extract_recordings_to_archive

app = create_app()

@app.cli.command('archive-extract')
@click.option('--term', default='May 2026', help='Term label to stamp on the rows')
def archive_extract(term):
    """Snapshot all Drive recording links into the recording_archive table."""
    added, skipped = extract_recordings_to_archive(term)
    click.echo(f'term={term}: added {added}, already present {skipped}')


if __name__ == '__main__':
    app.run(debug=True, port=3000)