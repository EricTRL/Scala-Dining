# Scala Dining

Cooking website.

## Set-up

### Local Python

- Create and activate an virtual environment
- Copy `.env.example` to `.env` and adjust as wanted
- `pip install -r requirements.txt -r dev-requirements.txt`
- `python manage.py migrate`
- `python manage.py runserver`

### Docker

- Install Docker and Docker Compose
- `docker-compose build`
- `docker-compose up`
- `docker-compose exec app python manage.py migrate`

## Development commands

* Lint code: `flake8`
* Run unit tests: `python manage.py test`
* Create superuser: `python manage.py createsuperuser`
* Coverage: `coverage run manage.py test`
  * Command line report: `coverage report`
  * Generate HTML report: `coverage html`


## Dependencies

To add a new dependency, append it to `requirements.in`, install `pip-tools`
inside the virtual environment
and run `pip-compile requirements.in`.
See [pip-tools documentation](https://github.com/jazzband/pip-tools)
for details.

## Code style

The linter Flake8 expects the code, including docstrings, to follow the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
See the file `.flake8` for the exact configuration.

To let PyCharm use the correct docstring format, change the setting at
"Tools -> Python Integrated Tools -> Docstrings -> Docstring format" to Google.
