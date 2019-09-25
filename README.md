# tubular

## Overview
Python scripts for integrating pipelines with various services/tools such as:
* Asgard
* Amazon Web Services EC2
* GitHub
* Jenkins
* Drupal

The scripts perform work to enable continuous delivery (CD) for https://edx.org. These scripts are called from various tasks/jobs/stages in GoCD pipelines - but could be called from any automation/CD framework.  

## How to run the scripts in this repo

The scripts in this repo are python Click scripts. You can learn more about Click here.
https://click.palletsprojects.com/en/7.x/

This is so that we can test them locally, and also run them as part of the deployment. You can view the documentation for each click command, and run it by doing the following:

```
virtualenv -p $(which python) .venv
source .venv/bin/activate
pip intsall -r requirements.txt
python scripts/my_script.py --help
python scripts/my_script.py --arg1 --arg2 --arg3
```


## Configuration
```
pip install -e .[dev]
```

## Testing
```
# Once, to install python versions:
cat .python-versions | xargs -n1 pyenv install

# Run the tests
tox
```

## License

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see ``LICENSE.txt`` for details.



## Environment variables

|     Variable Name    | Default                         | Description                                                                                   |
|:--------------------:|---------------------------------|-----------------------------------------------------------------------------------------------|
| ASGARD_API_ENDPOINTS | http://dummy.url:8091/us-east-1 | Fully qualified URL for the Asgard instance against which to run the scripts.                 |
| ASGARD_API_TOKEN     | dummy-token                     | String - The Asgard token.                                                                    |
| ASGARD_WAIT_TIMEOUT  | 600                             | Integer - Time in seconds to wait for an action such as instances healthy in a load balancer. |
| REQUESTS_TIMEOUT     | 10                              | How long to wait for an HTTP connection/response from Asgard.                                 |
| RETRY_MAX_ATTEMPTS   | 5                               | Integer - Maximum number of attempts to be made when Asgard returns an error.                 |
| RETRY_SAILTHRU_MAX_ATTEMPTS | 5                        | Integer - Maximum number of attempts to be made when Sailthru returns an error.               |
| RETRY_DELAY_SECONDS  | 5                               | Time in seconds to wait between retries to Asgard.                                            |
| RETRY_MAX_TIME_SECONDS | None                          | Time in seconds to keep retrying Asgard before giving up.                                     |
| RETRY_FACTOR         | 1.5                             | Factor by which to multiply the base wait time per retry attempt for EC2 boto calls.          |
| ASGARD_ELB_HEALTH_TIMEOUT | 600                        | Time in seconds to wait for an EC2 instance to become healthy in an ELB.                      |
| SHA_LENGTH           | 10                              | Length of the commit SHA to use when querying for a PR by commit.                             |
| BATCH_SIZE           | 18                              | Number of commits to batch together when querying a PR by commit.                             |

## Guidelines

Some general guidelines for tubular scripts:

* Prefer --my-argument to --my_argument
* Install your scripts by adding them to the console_scripts list in setup.cfg

## Status: Sustained
This codebase is currently sustained and maintained by the devops team, but not under any significant active development.  Retirement scripts are maintained by the Data engineering team.

## How to get help
edX employees can reach out for help by filing a devops support board ticket. edX employees can reach out for help by filing a devops support board ticket. https://openedx.atlassian.net/servicedesk/customer/portal/3  Open source bug fixes are welcome, but please review our contributors guide: https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/process/contributor.html before opening a pull request.  If you are adding significant features aside from bug fixes it might be a good idea to email devops devops@edx.org and ask before beginning the work as the compoonent is not under active development.

## How To Contribute

Contributions are welcome.

Please read [How To Contribute](https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst) for details.

Even though they were written with ```edx-platform``` in mind, the guidelines
should be followed for Open edX code in general.

## Reporting Security Issues

Please do not report security issues in public. Please email security@edx.org.