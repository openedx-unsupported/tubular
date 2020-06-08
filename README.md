# tubular

## Overview
Python scripts for integrating pipelines with various services/tools such as:
* Asgard
* Amazon Web Services EC2
* GitHub
* Jenkins
* Drupal

The scripts perform work to enable continuous delivery (CD) for https://edx.org. These scripts are called from various tasks/jobs/stages in GoCD pipelines - but could be called from any automation/CD framework.

## Configuration
```
pip install -e .[dev]
```

## Testing
```
# Once, to install python versions:
cat .python-version | xargs -n1 pyenv install

# Run the tests
tox
```

## License

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

## How To Contribute

Contributions are very welcome.

Please read [How To Contribute](https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst) for details.

Even though they were written with ```edx-platform``` in mind, the guidelines
should be followed for Open edX code in general.

## Reporting Security Issues

Please do not report security issues in public. Please email security@edx.org.

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
